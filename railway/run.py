"""Run a declared scenario and export reproducible mechanical/electrical accounts.
Example: python -m railway.run --output results/synthetic-1km
"""

import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .electrical import ElectricalParameters, regenerative_powers
from .integration import Settings, refined_settings
from .journey import Route, simulate_journey, validate_speed_cap
from .physics import Command, InfeasibleRun, Vehicle, forces

ROOT = Path(__file__).resolve().parents[1]


def load_scenario(path: Path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not config.get("scope") or not config.get("scenario_id"):
        raise ValueError("Scenario needs scope and scenario_id")
    if config.get("units") != "SI: m, s, kg, N, W, J":
        raise ValueError("Scenario must declare the supported SI unit convention")
    evidence = config.get("evidence", {})
    required = {*Vehicle.__dataclass_fields__, "route", "control", "settings"}
    if "electrical" in config:
        required.update(ElectricalParameters.__dataclass_fields__)
        if not isinstance(config["electrical"], dict) or any(value is None for value in config["electrical"].values()):
            raise ValueError("Unresolved electrical parameters cannot be used for a numerical scenario")
        ElectricalParameters(**config["electrical"])
    if "sensitivity" in config:
        required.add("sensitivity")
        electrical_sensitivity_cases(config)
    if required - evidence.keys() or any(not evidence[key].get("status") or not evidence[key].get("basis") for key in required):
        raise ValueError("Every active parameter group needs evidence status and basis")
    if any(value is None for value in config["vehicle"].values()):
        raise ValueError("Unresolved vehicle parameters cannot be used for a numerical scenario")
    train = Vehicle(**config["vehicle"])
    route = Route(**{key: tuple(tuple(row) for row in value) for key, value in config["route"].items()})
    settings = Settings(**config["settings"])
    validate_speed_cap(config["control"].get("cruise_speed_cap_mps"),
                       config["control"].get("initial_speed_mps", 0.0))
    if "mass_basis" in config:
        basis = config["mass_basis"]
        mass = basis["empty_mass_kg"] + basis["passengers"] * basis["passenger_mass_kg"]
        if abs(mass - train.mass_kg) > 1e-6 or abs(basis["empty_mass_kg"] * basis["rotating_fraction_of_tare"] - train.rotating_mass_kg) > 1e-6:
            raise ValueError("Vehicle masses disagree with declared mass basis")
    return config, train, route, settings


def summary(train, route, result):
    record = {
        "travel_time_s": float(result.time_s[-1]),
        "stop_error_m": float(result.states[0, -1] - route.length_m),
        "final_speed_mps": float(result.states[1, -1]),
        "peak_speed_mps": float(result.states[1].max()),
        "wheel_traction_work_j": float(result.states[2, -1]),
        "mechanical_brake_work_j": float(result.states[3, -1]),
        "resistance_work_j": float(result.states[4, -1]),
        "maximum_absolute_energy_residual_j": float(np.max(np.abs(result.energy_residual_j))),
        "maximum_speed_excess_mps": max(float(v) - route.speed_limit_mps(float(x))
                                         for x, v in zip(result.states[0], result.states[1])),
        "modes": sorted(set(result.modes)),
        "status": "Numerical synthetic study; physical calibration and validation pending",
    }
    if result.electrical is not None:
        record["electrical"] = {name: float(values[-1]) for name, values in vars(result.electrical).items()}
        record["electrical"]["maximum_absolute_balance_residual_j"] = float(
            np.max(np.abs(result.electrical.electrical_balance_residual_j)))
        record["electrical"]["boundary"] = "Train electrical terminals; net = import - export; no storage or network losses"
    return record


def electrical_parameters(config):
    return ElectricalParameters(**config["electrical"]) if "electrical" in config else None


def electrical_sensitivity_cases(config):
    """Declared parameter sweeps; regenerative limits use a receptive reference.

    Each tuple contains a label, electrical inputs and the comparison reference.
    Ranges are scenario assumptions, never probability or confidence bounds.
    """
    specification = config.get("sensitivity")
    if specification is None:
        return []
    if not isinstance(specification, dict) or not specification.get("scope"):
        raise ValueError("Sensitivity specification needs an explicit scope")
    baseline = electrical_parameters(config)
    if baseline is None:
        raise ValueError("Electrical sensitivity requires explicit electrical parameters")
    cases = []
    groups = [("electrical", baseline, "baseline")]
    if specification.get("regenerative"):
        if "regenerative_reference_acceptance_fraction" not in specification:
            raise ValueError("Regenerative sweeps need an explicit reference acceptance fraction")
        receptive = replace(baseline, regenerative_acceptance_fraction=
                            specification["regenerative_reference_acceptance_fraction"])
        cases.append(("regeneration_reference", receptive, "baseline"))
        groups.append(("regenerative", receptive, "regeneration_reference"))
    for group, reference, reference_name in groups:
        sweeps = specification.get(group, {})
        if not isinstance(sweeps, dict):
            raise ValueError(f"Sensitivity {group} must map parameter names to values")
        for name, values in sweeps.items():
            if name not in ElectricalParameters.__dataclass_fields__ or not isinstance(values, list) or not values:
                raise ValueError(f"Invalid electrical sensitivity sweep: {name}")
            for value in values:
                candidate = replace(reference, **{name: value})
                cases.append((f"{group}.{name}={value}", candidate, reference_name))
    return cases


def sensitivity(train, route, config, settings):
    """Deterministic one-at-a-time stress tests, not uncertainty/confidence bounds."""
    cases = [("baseline", train, route)]
    basis = config.get("mass_basis")
    if basis:
        for passengers in (0, 1628):
            cases.append((f"passengers_{passengers}", replace(train, mass_kg=basis["empty_mass_kg"] + passengers * basis["passenger_mass_kg"]), route))
    for factor in (0.8, 1.2):
        cases.extend([
            (f"resistance_x{factor}", replace(train, davis_a_n=train.davis_a_n*factor,
                                             davis_b_ns_per_m=train.davis_b_ns_per_m*factor,
                                             davis_c_ns2_per_m2=train.davis_c_ns2_per_m2*factor), route),
            (f"wheel_power_x{factor}", replace(train, wheel_power_w=train.wheel_power_w*factor), route),
            (f"traction_force_x{factor}", replace(train, traction_force_n=train.traction_force_n*factor), route),
            (f"service_brake_x{factor}", replace(train, service_brake_force_n=train.service_brake_force_n*factor), route),
            (f"rotating_mass_x{factor}", replace(train, rotating_mass_kg=train.rotating_mass_kg*factor), route),
        ])
    cases.append(("level_route", train, Route(((0, 0), (route.length_m, 0)), route.speed_limits_mps)))
    baseline_electrical = electrical_parameters(config)
    cases = [(label, vehicle, candidate_route, baseline_electrical, "baseline", "mechanical")
             for label, vehicle, candidate_route in cases]
    cases.extend((label, train, route, electrical, reference, "electrical")
                 for label, electrical, reference in electrical_sensitivity_cases(config))
    results = []
    references = {}
    for label, candidate, candidate_route, electrical, reference, category in cases:
        record = {"case": label, "category": category, "reference_case": reference,
                  "vehicle": asdict(candidate), "route": asdict(candidate_route),
                  "electrical_parameters": asdict(electrical) if electrical is not None else None}
        try:
            run = simulate_journey(candidate, candidate_route, settings=settings,
                                   electrical=electrical, **config["control"])
            record.update(summary(candidate, candidate_route, run))
            references[label] = record
            if label != "baseline" and reference in references:
                parent = references[reference]
                record["travel_time_change_s"] = record["travel_time_s"] - parent["travel_time_s"]
                if electrical is not None:
                    record["net_supply_energy_change_j"] = (record["electrical"]["net_supply_energy_j"] -
                                                             parent["electrical"]["net_supply_energy_j"])
                if category == "electrical":
                    record["changed_electrical_parameters"] = {
                        key: value for key, value in asdict(electrical).items()
                        if value != parent["electrical_parameters"][key]}
        except InfeasibleRun as error:
            record.update(status="infeasible", reason=str(error))
        results.append(record)
    return results


def convergence(train, route, config, settings, baseline):
    """Refine both numerical passes; compare time and nonzero mechanical work."""
    fine_settings = refined_settings(settings)
    refined = simulate_journey(train, route, settings=fine_settings,
                               electrical=electrical_parameters(config), **config["control"])
    first, second = summary(train, route, baseline), summary(train, route, refined)
    metrics = ["travel_time_s", "wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j"]
    changes = {key: abs(first[key] - second[key]) / max(abs(second[key]), 1.0) for key in metrics}
    if baseline.electrical is not None:
        for key, values in vars(baseline.electrical).items():
            if key == "electrical_balance_residual_j":
                continue
            value = float(getattr(refined.electrical, key)[-1])
            changes[f"electrical.{key}"] = abs(float(values[-1]) - value) / max(abs(value), 1.0)
    if max(changes.values()) >= 0.005:
        raise RuntimeError("Numerical refinement exceeds the 0.5% convergence target")
    return {"refined_settings": asdict(fine_settings), "refined_summary": second,
            "relative_changes": changes, "acceptance_relative_change": 0.005}


def provenance(config):
    """Inputs and source digests used by saved runs and declared experiments."""
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    inputs = {"configuration": config, "code_sha256": source_hashes,
              "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}}
    if config.get("reference_file"):
        inputs["reference_file_sha256"] = hashlib.sha256((ROOT / config["reference_file"]).read_bytes()).hexdigest()
    return inputs


def export_run(config, train, route, settings, result, target, *, overwrite=False,
               check_convergence=False, include_sensitivity=False):
    """Save an existing replay through the same exporter as the scenario CLI."""
    target = Path(target)
    names = ["trajectory.csv", "run.json"] + (["sensitivity.json"] if include_sensitivity else [])
    if not overwrite and any((target / name).exists() for name in names):
        raise FileExistsError("Output files already exist; choose another directory or pass --overwrite")
    # Ensure the exported settings describe the actual replay, including refined runs.
    config = {**config, "settings": asdict(settings)}
    inputs = provenance(config)
    run_id = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    record = {"run_id": run_id, **inputs, "summary": summary(train, route, result),
              "phases": [asdict(phase) for phase in result.phases]}
    if check_convergence:
        record["convergence"] = convergence(train, route, config, settings, result)
    variations = sensitivity(train, route, config, settings) if include_sensitivity else None
    target.mkdir(parents=True, exist_ok=True)
    columns = ["time_s", "position_m", "speed_mps", "height_m", "mode", "acceleration_mps2",
               "traction_force_n", "brake_force_n", "resistance_n", "grade_force_n", "wheel_traction_power_w",
               "wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j", "energy_residual_j"]
    electrical_columns = [] if result.electrical is None else list(vars(result.electrical))
    columns.extend(electrical_columns)
    if electrical_columns:
        columns.append("regenerative_accepted_power_w")
    parameters = electrical_parameters(config)
    with (target / "trajectory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for i, (time, state, mode, slope) in enumerate(zip(result.time_s, result.states.T, result.modes, result.slopes)):
            x, speed, wt, wb, wr = state
            f = forces(train, max(float(speed), 0), float(slope), Command(mode))
            accepted_power = ([] if parameters is None else
                              [regenerative_powers(parameters, f.brake_n, max(float(speed), 0)).wheel_power_w *
                               parameters.regenerative_efficiency])
            writer.writerow([time, x, speed, result.heights_m[i], mode, f.acceleration_mps2,
                             f.traction_n, f.brake_n, f.resistance_n, f.grade_n, f.traction_n * speed,
                             wt, wb, wr, result.energy_residual_j[i],
                             *(getattr(result.electrical, name)[i] for name in electrical_columns),
                             *accepted_power])
    record["trajectory_sha256"] = hashlib.sha256((target / "trajectory.csv").read_bytes()).hexdigest()
    (target / "run.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if variations is not None:
        (target / "sensitivity.json").write_text(json.dumps({"purpose": "Hypothetical stress tests, not measured uncertainty or operational savings", "baseline_run_id": run_id, "specification": config.get("sensitivity"), "cases": variations}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "data/scenarios/synthetic-1km.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/synthetic-1km")
    parser.add_argument("--overwrite", action="store_true", help="Replace this command's named output files")
    parser.add_argument("--sensitivity", action="store_true", help="Also run declared parameter stress tests")
    parser.add_argument("--convergence", action="store_true", help="Refine planning and time integration and record comparisons")
    args = parser.parse_args()
    config, train, route, settings = load_scenario(args.scenario)
    names = ["run.json", "trajectory.csv"] + (["sensitivity.json"] if args.sensitivity else [])
    if not args.overwrite and any((args.output / name).exists() for name in names):
        parser.error("Output files already exist; choose another directory or pass --overwrite")
    result = simulate_journey(train, route, settings=settings,
                              electrical=electrical_parameters(config), **config["control"])
    record = export_run(config, train, route, settings, result, args.output, overwrite=args.overwrite,
                        check_convergence=args.convergence, include_sensitivity=args.sensitivity)
    print(json.dumps({"run_id": record["run_id"], **record["summary"]}, indent=2))
    print(f"Wrote results to {args.output}")


if __name__ == "__main__":
    main()
