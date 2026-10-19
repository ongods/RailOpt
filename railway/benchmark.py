"""Reproducible coasting sweep, feasibility audit and sampled energy-time frontier.

Run with: python -m railway.benchmark --output results/coasting-benchmark
No solver or driving-policy changes are made by this experiment.
"""

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .audit import audit_profile
from .integration import refined_settings
from .journey import simulate_journey
from .physics import InfeasibleRun, finite
from .run import ROOT, electrical_parameters, load_scenario, summary


def validate_experiment(specification, route):
    """Reject malformed switches before treating any policy as infeasible."""
    if not specification.get("experiment_id") or not specification.get("scope"):
        raise ValueError("Benchmark requires experiment_id and scope")
    evidence = specification.get("evidence", {})
    if not evidence.get("status") or not evidence.get("basis"):
        raise ValueError("Benchmark needs evidence status and basis for its choices")
    positions = specification.get("coast_positions_m")
    if not isinstance(positions, list) or not positions:
        raise ValueError("coast_positions_m must be a nonempty list")
    for value in positions:
        finite("coast position", value, 0)
        if value >= route.length_m:
            raise ValueError("Every coast position must be within the route")
    if positions != sorted(set(positions)):
        raise ValueError("Coast positions must be unique and increasing")
    for value in specification.get("refine_coast_positions_m", []):
        if value not in positions:
            raise ValueError("Refinement probes must be in the coast grid")
    for key in ("time_s", "energy_j"):
        finite(f"dominance {key}", specification["dominance_tolerances"][key], 0)


def classify_frontier(cases, time_tolerance_s, energy_tolerance_j):
    """Mark sampled dominance; keep numerical ties and exclude rejected runs.

    A dominates B if neither objective worsens beyond its tolerance and at least
    one improves beyond tolerance. These are numerical comparison bands only.
    """
    feasible = [case for case in cases if case["status"] == "feasible"]
    for case in cases:
        case["dominated_by"] = []
        case["on_sampled_frontier"] = False
    for case in feasible:
        t, energy = case["summary"]["travel_time_s"], case["summary"]["electrical"]["net_supply_energy_j"]
        for other in feasible:
            ot = other["summary"]["travel_time_s"]
            oe = other["summary"]["electrical"]["net_supply_energy_j"]
            if (ot <= t + time_tolerance_s and oe <= energy + energy_tolerance_j
                    and (ot < t - time_tolerance_s or oe < energy - energy_tolerance_j)):
                case["dominated_by"].append(other["case_id"])
        case["on_sampled_frontier"] = not case["dominated_by"]


def run_benchmark(train, route, config, settings, specification):
    """Simulate the declared controls, audit them, and refine representative runs.

    Only InfeasibleRun is classified as a policy rejection. Software/integration
    failures propagate, rather than masquerading as physical infeasibility.
    """
    validate_experiment(specification, route)
    electrical = electrical_parameters(config)
    if electrical is None:
        raise ValueError("The energy-time benchmark requires an electrical scenario")
    scenario_coast = config["control"].get("coast_from_m")
    switches = sorted(set(specification["coast_positions_m"] +
                          ([] if scenario_coast is None else [scenario_coast])))
    cases = []
    for coast in [None, *switches]:
        control = {**config["control"], "coast_from_m": coast}
        case_id = "no_coast" if coast is None else f"coast_{coast}m"
        record = {"case_id": case_id, "control": control, "scenario_control": coast == scenario_coast}
        try:
            result = simulate_journey(train, route, settings=settings, electrical=electrical, **control)
        except InfeasibleRun as error:
            record.update(status="infeasible_policy", reason=str(error))
        else:
            audit = audit_profile(train, route, settings, result, electrical, control.get("cruise_speed_cap_mps"))
            record.update(status="feasible" if audit["passed"] else "audit_failed",
                          audit=audit, summary=summary(train, route, result),
                          phases=[asdict(phase) for phase in result.phases])
        cases.append(record)

    # Always check reference controls, sampled extrema and the coarse rejection
    # boundary, as well as the experiment's explicit probes.
    selected = {case["case_id"] for case in cases if case["scenario_control"] or
                case["control"]["coast_from_m"] is None or
                case["control"]["coast_from_m"] in specification.get("refine_coast_positions_m", [])}
    feasible = [case for case in cases if case["status"] == "feasible"]
    if feasible:
        for key in (lambda case: case["summary"]["travel_time_s"],
                    lambda case: -case["summary"]["travel_time_s"],
                    lambda case: case["summary"]["electrical"]["net_supply_energy_j"]):
            selected.add(min(feasible, key=key)["case_id"])
    rejected = [case for case in cases if case["status"] == "infeasible_policy"]
    if rejected:
        selected.add(max(rejected, key=lambda case: case["control"]["coast_from_m"] or 0)["case_id"])
    fine_settings = refined_settings(settings)
    for case in cases:
        if case["case_id"] not in selected:
            continue
        try:
            fine = simulate_journey(train, route, settings=fine_settings, electrical=electrical, **case["control"])
        except InfeasibleRun as error:
            passed = case["status"] == "infeasible_policy"
            case["refinement"] = {"passed": passed, "status": "infeasible_policy", "reason": str(error)}
        else:
            audit = audit_profile(train, route, fine_settings, fine, electrical, case["control"].get("cruise_speed_cap_mps"))
            fine_summary = summary(train, route, fine)
            changes = {}
            if case["status"] == "feasible":
                first = case["summary"]
                for name in ("travel_time_s", "wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j"):
                    changes[name] = abs(first[name] - fine_summary[name]) / max(abs(fine_summary[name]), 1.0)
                for name, value in first["electrical"].items():
                    if name.endswith("_j") and "residual" not in name:
                        changes[f"electrical.{name}"] = abs(value - fine_summary["electrical"][name]) / max(abs(fine_summary["electrical"][name]), 1.0)
            passed = case["status"] == "feasible" and audit["passed"] and max(changes.values(), default=0) < 0.005
            case["refinement"] = {"passed": passed, "status": "feasible" if audit["passed"] else "audit_failed",
                                  "relative_changes": changes, "summary": fine_summary, "audit": audit}
        if not passed:
            case["coarse_status"] = case["status"]
            case["status"] = "refinement_failed"
    tolerances = specification["dominance_tolerances"]
    classify_frontier(cases, tolerances["time_s"], tolerances["energy_j"])
    return {"cases": cases, "counts": dict(Counter(case["status"] for case in cases)),
            "refined_settings": asdict(fine_settings), "refinement_acceptance_relative_change": 0.005,
            "refined_case_ids": sorted(selected),
            "sampled_frontier_ids": [case["case_id"] for case in cases if case["on_sampled_frontier"]]}


def feasibility_report(record):
    """Standalone reading report; raw SI evidence is retained in benchmark.json."""
    cases = record["cases"]
    lines = ["# Coasting benchmark: feasibility and energy-time tradeoff", "",
             f"Benchmark ID: `{record['benchmark_id']}`. Scenario: `{record['configuration']['scenario_id']}`.", "",
             record["experiment"]["scope"], "",
             "Only the coast request changes. Braking and speed constraints take priority. No journey-time target is imposed; the configured maximum time is a timeout.", "",
             "![Energy-time plot](energy-time.png)", "",
             "Net energy is train-terminal import minus export, including auxiliary consumption over the actual journey. Values below use J / 3,600,000 for kWh. Potential regeneration is not credited as accepted recovery.", "",
             "## Feasibility", "", f"Status counts: `{json.dumps(record['counts'], sort_keys=True)}`.", "",
             "Feasible means the planner/time replay completed and the separate audit passed. An infeasible policy is a rejection under this fixed driving policy, not proof that the train cannot traverse the route. Audit or refinement failures are excluded from the frontier. Unexpected solver/software errors abort the benchmark.", "",
             "Audits check finite states, increasing time, forward motion, terminal position/speed, local speed limits, force/power envelopes, exclusive commands, nondecreasing work, bounded recovery/export and independent mechanical/full train-boundary energy closure. Checks cover accepted solver samples and one-sided phase boundaries; they are not a continuous-time proof.", "",
             "| Coast request (m) | Status | Time (s) | Net energy (kWh) | Brake work (MJ) | Sampled frontier | Refinement |",
             "| --- | --- | ---: | ---: | ---: | --- | --- |"]
    for case in cases:
        coast = case["control"]["coast_from_m"]
        label = "No coast" if coast is None else f"{coast:g}"
        refinement = case.get("refinement")
        refined = "not selected" if refinement is None else ("passed" if refinement["passed"] else "FAILED")
        if "summary" in case:
            s = case["summary"]
            values = f"{s['travel_time_s']:.4f} | {s['electrical']['net_supply_energy_j']/3.6e6:.5f} | {s['mechanical_brake_work_j']/1e6:.4f}"
        else:
            values = "— | — | —"
        lines.append(f"| {label} | {case['status']} | {values} | {'yes' if case['on_sampled_frontier'] else 'no'} | {refined} |")
    lines.extend(["", "## Rejections and failures", ""])
    rejected = [case for case in cases if case["status"] != "feasible"]
    if not rejected:
        lines.append("None in this declared sweep.")
    for case in rejected:
        reason = case.get("reason", ", ".join(key for key, value in case.get("audit", {}).get("checks", {}).items() if not value))
        if case["status"] == "refinement_failed":
            reason = "Coarse/refined feasibility, audit or energy/time refinement disagrees; see the JSON record."
        lines.append(f"- `{case['case_id']}`: {reason}")
    lines.extend(["", "## Numerical checks and interpretation", "",
                  f"{len(record['refined_case_ids'])} representative cases were rerun with half the time/planning steps and tenfold tighter tolerances. Time, mechanical work and electrical energy totals must change by less than 0.5%, and refined replays must pass their audits. Rejected probes must remain rejected. The grid near the feasibility boundary is sampled, not a located mathematical threshold.", "",
                  "Dominance uses the declared time/energy tolerance bands: another feasible sample must be no worse within either band and better beyond at least one. Numerical ties remain on the sampled frontier. Grid spacing, the one-switch policy and selected assumptions limit the frontier; no continuous global optimum is established.", "",
                  "Lower energy at a longer journey time is a tradeoff, not equal-time savings or measured railway improvement. Fixed-time optimization requires a target/tolerance and a richer control parameterization. Physical calibration/validation, brake delays, jerk and real route/electrical inputs remain outside this synthetic benchmark.", "",
                  "Full inputs, provenance, SI metrics, per-case controls/phases, individual checks, dominance witnesses and refined results are in `benchmark.json`; `profiles.csv` is a flat comparison table.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "data/experiments/coasting-benchmark.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/coasting-benchmark")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    names = ("benchmark.json", "profiles.csv", "energy-time.png", "energy-time.svg", "coasting-feasibility.md")
    if not args.overwrite and any((args.output / name).exists() for name in names):
        parser.error("Output files already exist; choose another directory or pass --overwrite")
    try:
        plotting_version = version("matplotlib")
    except PackageNotFoundError:
        parser.error("Plotting requires: python -m pip install -r requirements.txt")
    specification = json.loads(args.experiment.read_text(encoding="utf-8"))
    config, train, route, settings = load_scenario(ROOT / specification["scenario_file"])
    inputs = {"experiment": specification, "configuration": config,
              "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(Path(__file__).parent.glob("*.py"))},
              "software": {"python": platform.python_version(), "numpy": np.__version__,
                           "scipy": scipy.__version__, "matplotlib": plotting_version}}
    if config.get("reference_file"):
        inputs["reference_file_sha256"] = hashlib.sha256((ROOT / config["reference_file"]).read_bytes()).hexdigest()
    benchmark_id = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    print(f"Running coasting benchmark {benchmark_id}", flush=True)
    record = {"benchmark_id": benchmark_id, **inputs,
              **run_benchmark(train, route, config, settings, specification)}
    args.output.mkdir(parents=True, exist_ok=True)
    from .plotting import plot_energy_time
    plot_energy_time(record, args.output)
    (args.output / "benchmark.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    columns = ["case_id", "coast_from_m", "status", "reason", "on_sampled_frontier", "dominated_by",
               "travel_time_s", "net_supply_energy_j", "wheel_traction_work_j", "mechanical_brake_work_j",
               "resistance_work_j", "stop_error_m", "final_speed_mps", "maximum_speed_excess_mps",
               "maximum_mechanical_balance_residual_j", "maximum_system_balance_residual_j", "refinement_passed"]
    with (args.output / "profiles.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for case in record["cases"]:
            row = {key: case[key] for key in ("case_id", "status", "on_sampled_frontier")}
            row.update(coast_from_m=case["control"]["coast_from_m"], reason=case.get("reason", ""),
                       dominated_by=json.dumps(case["dominated_by"]),
                       refinement_passed=case.get("refinement", {}).get("passed", ""))
            if "summary" in case:
                row.update({key: value for key, value in case["summary"].items() if key in columns})
                row["net_supply_energy_j"] = case["summary"]["electrical"]["net_supply_energy_j"]
                row.update({key: value for key, value in case["audit"]["metrics"].items() if key in columns})
            writer.writerow(row)
    (args.output / "coasting-feasibility.md").write_text(feasibility_report(record), encoding="utf-8")
    print(json.dumps({"benchmark_id": benchmark_id, "counts": record["counts"],
                      "refined_cases": len(record["refined_case_ids"]),
                      "sampled_frontier_cases": len(record["sampled_frontier_ids"])}, indent=2))
    print(f"Wrote benchmark, plot and report to {args.output}")
    if any(case["status"] in {"audit_failed", "refinement_failed"} for case in record["cases"]):
        raise SystemExit("Benchmark contains audit/refinement failures; inspect the report")


if __name__ == "__main__":
    main()
