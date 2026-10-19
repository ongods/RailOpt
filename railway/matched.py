"""Bounded matched-arrival search using the existing single-train simulator.

python -m railway.matched --output results/matched-time
"""

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .audit import audit_profile
from .integration import refined_settings
from .journey import simulate_journey
from .physics import InfeasibleRun, finite
from .run import ROOT, electrical_parameters, export_run, load_scenario, provenance, summary


def net_energy_j(case):
    """Final train-terminal import minus export for one completed profile [J]."""
    return case["summary"]["electrical"]["net_supply_energy_j"]


def energy_ranking(reference_minus_candidate_j, tolerance_j):
    """Keep differences within the declared numerical band indistinguishable."""
    if reference_minus_candidate_j > tolerance_j:
        return "candidate_lower"
    if reference_minus_candidate_j < -tolerance_j:
        return "reference_lower"
    return "indistinguishable"


def validate_experiment(spec, route):
    if not spec.get("experiment_id") or not spec.get("scope"):
        raise ValueError("Experiment needs an ID and scope")
    if not all(spec.get("evidence", {}).get(key) for key in ("status", "basis")):
        raise ValueError("Experiment choices need evidence status and basis")
    for key in ("target_time_s", "arrival_tolerance_s", "search_energy_tolerance_j"):
        finite(key, spec[key], 0)
        if spec[key] == 0:
            raise ValueError(f"{key} must be positive")
    finite("ranking_tolerance_j", spec["ranking_tolerance_j"], 0)
    for key in ("auxiliary_power_w", "regenerative_acceptance_fraction"):
        values = spec.get("robustness", {}).get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Robustness requires nonempty {key}")
        for value in values:
            finite(key, value, 0)
            if key == "regenerative_acceptance_fraction" and value > 1:
                raise ValueError("regenerative_acceptance_fraction must be <= 1")
    for key in ("cruise_speed_caps_mps", "coast_positions_m"):
        values = spec[key]
        if not isinstance(values, list) or len(values) < 2 or values != sorted(set(values)):
            raise ValueError(f"{key} needs at least two unique increasing samples")
        for value in values:
            finite(key, value, 0)
            if (key == "cruise_speed_caps_mps" and value == 0 or
                    key == "coast_positions_m" and value >= route.length_m):
                raise ValueError(f"Invalid {key}")
    iterations = spec["crossing_iterations"]
    if not isinstance(iterations, int) or not 1 <= iterations <= 20:
        raise ValueError("crossing_iterations must be an integer in [1, 20]")


def evaluate(train, route, config, settings, spec, control):
    """Policy rejections, arrival failures and failed audits remain distinct."""
    electrical = electrical_parameters(config)
    record = {"control": control}
    try:
        result = simulate_journey(train, route, settings=settings, electrical=electrical, **control)
    except InfeasibleRun as error:
        return {**record, "status": "infeasible_policy", "reason": str(error)}, None
    audit = audit_profile(train, route, settings, result, electrical, control.get("cruise_speed_cap_mps"))
    error = float(result.time_s[-1]) - spec["target_time_s"]
    record.update(summary=summary(train, route, result), audit=audit, arrival_error_s=error,
                  status=("audit_failed" if not audit["passed"] else
                          "feasible" if abs(error) <= spec["arrival_tolerance_s"] else "time_infeasible"))
    return record, result


def search(train, route, config, settings, spec, caps, coasts):
    """Sample a 2D grid and bisect each observed adjacent target-time crossing.

    Bisection is local to a sampled sign-changing interval. Every new point is
    simulated and audited; no interpolated point is declared feasible. Multiple
    crossings are retained, and no global monotonicity is assumed.
    """
    cache = {}

    def probe(cap, coast):
        key = (float(cap), coast)
        if key not in cache:
            control = {**config["control"], "cruise_speed_cap_mps": float(cap), "coast_from_m": coast}
            cache[key] = evaluate(train, route, config, settings, spec, control)[0]
        return cache[key]

    for coast in [None, *coasts]:
        samples = [probe(cap, coast) for cap in caps]
        for left, right in zip(samples, samples[1:]):
            if not all(case.get("audit", {}).get("passed") for case in (left, right)):
                continue
            if left["arrival_error_s"] * right["arrival_error_s"] >= 0:
                continue
            for _ in range(spec["crossing_iterations"]):
                mid = probe((left["control"]["cruise_speed_cap_mps"] +
                             right["control"]["cruise_speed_cap_mps"]) / 2, coast)
                if not mid.get("audit", {}).get("passed"):
                    break
                if left["arrival_error_s"] * mid["arrival_error_s"] <= 0:
                    right = mid
                else:
                    left = mid
    cases = list(cache.values())
    selected = {}
    for name, requested_coast in (("reference", False), ("candidate", True)):
        feasible = [case for case in cases if case["status"] == "feasible" and
                    (case["control"]["coast_from_m"] is not None) == requested_coast]
        selected[name] = min(feasible, key=net_energy_j, default=None)
    return {"cases": cases, "counts": dict(Counter(c["status"] for c in cases)), **selected}


def verify(train, route, config, settings, spec, case):
    """Replay serialized controls independently, then refine both numerical passes."""
    control = json.loads(json.dumps(case["control"], allow_nan=False))
    replay, result = evaluate(train, route, config, settings, spec, control)
    fine, _ = evaluate(train, route, config, refined_settings(settings), spec, control)
    changes = {}
    if "summary" in replay and "summary" in fine:
        for key in ("travel_time_s", "wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j"):
            changes[key] = abs(replay["summary"][key] - fine["summary"][key]) / max(abs(fine["summary"][key]), 1)
        for key, value in fine["summary"]["electrical"].items():
            if key.endswith("_j") and "residual" not in key:
                changes[key] = abs(replay["summary"]["electrical"][key] - value) / max(abs(value), 1)
    passed = (case["status"] == replay["status"] == fine["status"] == "feasible" and
              replay.get("summary") == case.get("summary") and max(changes.values(), default=1) < 0.005)
    return {"passed": passed, "replay": replay, "refined": fine, "relative_changes": changes}, result


def compare(train, route, config, settings, spec):
    validate_experiment(spec, route)
    if electrical_parameters(config) is None or config["control"].get("initial_speed_mps", 0) != 0:
        raise ValueError("Matched study requires an electrical, rest-to-rest scenario")
    caps, coasts = spec["cruise_speed_caps_mps"], spec["coast_positions_m"]
    coarse = search(train, route, config, settings, spec, caps, coasts)
    # Halve both grid spacings over the same bounds; this is search resolution,
    # separate from the finer integration in verify().
    def subdivide(values):
        return sorted([*values, *((a + b) / 2 for a, b in zip(values, values[1:]))])
    fine = search(train, route, config, settings, spec, subdivide(caps), subdivide(coasts))
    record = {"status": "no_feasible_comparison_within_tested_bounds", "coarse_search": coarse,
              "refined_search": fine, "refined_settings": asdict(refined_settings(settings))}
    runs = {}
    if any(fine[name] is None for name in ("reference", "candidate")):
        return record, runs
    checks = {}
    for name in ("reference", "candidate"):
        checks[name], runs[name] = verify(train, route, config, settings, spec, fine[name])
    difference = net_energy_j(fine["reference"]) - net_energy_j(fine["candidate"])
    threshold = spec["search_energy_tolerance_j"]
    resolution = {"passed": False, "tolerance_j": threshold}
    if all(coarse[name] is not None for name in checks):
        coarse_difference = net_energy_j(coarse["reference"]) - net_energy_j(coarse["candidate"])
        changes = {name: abs(net_energy_j(coarse[name]) - net_energy_j(fine[name])) for name in checks}
        stable = (max(changes.values()) <= threshold and
                  energy_ranking(coarse_difference, threshold) == energy_ranking(difference, threshold))
        resolution.update(passed=stable, energy_changes_j=changes,
                          coarse_energy_difference_j=coarse_difference)
    else:
        resolution["reason"] = "A feasible pair was found only after grid refinement; search stability is unverified"
    record.update(verification=checks, search_resolution=resolution,
                  energy_difference_j=difference, ranking=energy_ranking(difference, threshold),
                  arrival_time_difference_s=fine["candidate"]["summary"]["travel_time_s"] -
                                            fine["reference"]["summary"]["travel_time_s"])
    verified = resolution["passed"] and all(check["passed"] for check in checks.values())
    record["status"] = "verified_comparison" if verified else "verification_failed"
    return record, runs


def robustness(train, route, config, settings, spec, comparison):
    """Replay fixed nominal controls: no retuning under changed assumptions."""
    cases = []
    if comparison["status"] != "verified_comparison":
        return {"mode": "fixed_nominal_controls", "status": "no_verified_pair", "cases": []}
    for auxiliary in spec["robustness"]["auxiliary_power_w"]:
        for acceptance in spec["robustness"]["regenerative_acceptance_fraction"]:
            electrical = {**config["electrical"], "auxiliary_power_w": auxiliary,
                          "regenerative_acceptance_fraction": acceptance}
            changed = {**config, "electrical": electrical}
            electrical_parameters(changed)
            pair = {}
            for name in ("reference", "candidate"):
                control = comparison["refined_search"][name]["control"]
                case, _ = evaluate(train, route, changed, settings, spec, control)
                checked, _ = verify(train, route, changed, settings, spec, case)
                pair[name] = {**case, "verification": checked}
            passed = all(p["verification"]["passed"] for p in pair.values())
            delta = net_energy_j(pair["reference"]) - net_energy_j(pair["candidate"]) if passed else None
            # Refinement changes provide an empirical comparison band, not a rigorous error bound.
            uncertainty = sum(abs(p["summary"]["electrical"]["net_supply_energy_j"] -
                                  p["verification"]["refined"]["summary"]["electrical"]["net_supply_energy_j"])
                              for p in pair.values()) if passed else None
            tolerance = max(spec["ranking_tolerance_j"], uncertainty) if passed else None
            rank = energy_ranking(delta, tolerance) if passed else "unverified_or_time_infeasible"
            cases.append({"auxiliary_power_w": auxiliary, "regenerative_acceptance_fraction": acceptance,
                          "pair": pair, "energy_difference_j": delta, "numerical_tolerance_j": tolerance, "ranking": rank})
    return {"mode": "fixed_nominal_controls; neither strategy retuned", "cases": cases,
            "ranking_counts": dict(Counter(c["ranking"] for c in cases))}


def report(record):
    study = record["comparison"]
    interpretation = (
        "This is the best feasible tested profile in the declared bounds and parameterization. "
        "Unobserved crossings and finer search regions may exist."
        if study["status"] == "verified_comparison" else
        "No verified comparison is established. Any selected profiles are provisional; "
        "inspect the search and verification records before interpreting energy differences."
    )
    lines = ["# Matched-time synthetic comparison", "", f"Experiment ID: `{record['experiment_id']}`.", "",
             record["experiment"]["scope"], "", f"Status: **{study['status']}**.", "",
             "Objective: minimum net train-terminal import minus export, including actual-duration auxiliaries. "
             "Controls: cruise-speed ceiling and one coast position. No waiting is added. "
             "Physical limits and timeout remain independent of the arrival requirement.", "",
             f"Target {record['experiment']['target_time_s']} s +/- {record['experiment']['arrival_tolerance_s']} s.", "",
             "| Profile | Cap (m/s) | Coast (m) | Arrival (s) | Arrival error (s) | Net (kWh) |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name in ("reference", "candidate"):
        case = study["refined_search"][name]
        if case:
            s, c = case["summary"], case["control"]
            lines.append(f"| {name} | {c['cruise_speed_cap_mps']:.6f} | {c['coast_from_m']} | "
                         f"{s['travel_time_s']:.6f} | {case['arrival_error_s']:.6f} | {s['electrical']['net_supply_energy_j']/3.6e6:.6f} |")
    if "energy_difference_j" in study:
        lines += ["", f"Reference minus candidate: {study['energy_difference_j']/3.6e6:.6f} kWh. "
                  f"Candidate minus reference arrival: {study['arrival_time_difference_s']:.6f} s.", "",
                  f"Search-resolution check: `{json.dumps(study['search_resolution'], sort_keys=True)}`."]
    lines += ["", "Every accepted sample passes the existing independent constraint and energy audit. "
              "Selected controls are serialized, replayed again and checked with half the time/distance steps and "
              "tenfold tighter tolerances. Both arrival errors must remain within tolerance; work/energy changes "
              "must remain below 0.5%. Grid refinement is a separate empirical search-resolution check.", "",
              interpretation + " A failed search does not prove global "
              "infeasibility. These are hypothetical simulations, not measured railway savings.", "",
              "## Fixed-control robustness", "",
              "Auxiliary/acceptance combinations replay both nominal controls without retuning. "
              "Ranges are hypothetical choices, not confidence intervals. Numerical ranking tolerance is the "
              "larger of the declared band and the sum of both energy-refinement changes.", "",
              "| Aux (kW) | Acceptance | Reference minus candidate (kWh) | Ranking |",
              "| ---: | ---: | ---: | --- |"]
    for case in record.get("robustness", {}).get("cases", []):
        value = case["energy_difference_j"]
        text = "unverified" if value is None else f"{value/3.6e6:.6f}"
        lines.append(f"| {case['auxiliary_power_w']/1000:g} | {case['regenerative_acceptance_fraction']:g} | {text} | {case['ranking']} |")
    return "\n".join([*lines, "", "Full bounds, samples, rejection reasons, audits, controls, settings and provenance are in comparison.json.", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "data/experiments/matched-time.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/matched-time")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    names = ("comparison.json", "comparison.md", "comparison.png", "comparison.svg",
             "reference/run.json", "reference/trajectory.csv", "candidate/run.json", "candidate/trajectory.csv")
    if not args.overwrite and any((args.output / name).exists() for name in names):
        parser.error("Output files already exist; choose another directory or pass --overwrite")
    spec = json.loads(args.experiment.read_text(encoding="utf-8"))
    config, train, route, settings = load_scenario(ROOT / spec["scenario_file"])
    inputs = {**provenance(config), "experiment": spec}
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    print(f"Running matched-time search {identity}", flush=True)
    comparison, runs = compare(train, route, config, settings, spec)
    record = {"experiment_id": identity, **inputs, "comparison": comparison,
              "robustness": robustness(train, route, config, settings, spec, comparison)}
    args.output.mkdir(parents=True, exist_ok=True)
    if comparison["status"] == "verified_comparison":
        record["saved_runs"] = {}
        for name, run in runs.items():
            selected_config = {**config, "control": comparison["refined_search"][name]["control"]}
            saved = export_run(selected_config, train, route, settings, run, args.output / name, overwrite=args.overwrite)
            record["saved_runs"][name] = {"run_id": saved["run_id"], "trajectory_sha256": saved["trajectory_sha256"]}
        from .plotting import plot_matched
        plot_matched(record, runs, route, args.output)
    (args.output / "comparison.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (args.output / "comparison.md").write_text(report(record), encoding="utf-8")
    print(json.dumps({"experiment_id": identity, "status": comparison["status"],
                      "robustness": record["robustness"].get("ranking_counts")}, indent=2))
    if comparison["status"] != "verified_comparison":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
