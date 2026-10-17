"""Offline analytical feasibility checks; deliberately contains no train ODE solver.

Run: python scripts/research/preflight.py
Optionally writes screening CSVs with --output results/preflight.
Only the Python standard library is required.
"""

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
G = 9.80665


def check_close(actual, expected):
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-6):
        raise ValueError(f"Analytical fixture mismatch: {actual} != {expected}")


def check_fixtures():
    fixtures = json.loads((ROOT / "data/verification/analytical-fixtures.json").read_text())
    for case in fixtures["cases"]:
        mass = case["mass_kg"]
        effective = mass + case["rotating_mass_kg"]
        initial = case["initial_speed_mps"]
        if case["id"] == "lossless-downhill-coast":
            potential = mass * G * case["height_change_m"]
            check_close(potential, case["expected_potential_energy_change_j"])
            check_close(initial**2 - 2 * potential / effective,
                        case["expected_final_speed_squared_m2ps2"])
        elif case["id"] == "constant-power-above-transition":
            transition = case["wheel_power_w"] / case["maximum_force_n"]
            if initial < transition:
                raise ValueError("Constant-power fixture begins below its power region")
            work = case["wheel_power_w"] * case["duration_s"]
            check_close(initial**2 + 2 * work / effective,
                        case["expected_final_speed_squared_m2ps2"])
            check_close(work, case["expected_traction_work_j"])
        else:
            force = case["traction_force_n"] - case["brake_force_n"] - case["resistance_n"]
            acceleration = force / effective
            if "expected_stop_time_s" in case:
                duration = -initial / acceleration
                distance = initial * duration + acceleration * duration**2 / 2
                check_close(duration, case["expected_stop_time_s"])
                check_close(distance, case["expected_stop_distance_m"])
                check_close(case["brake_force_n"] * distance, case["expected_brake_work_j"])
            else:
                duration = case["duration_s"]
                distance = initial * duration + acceleration * duration**2 / 2
                check_close(initial + acceleration * duration, case["expected_speed_mps"])
                check_close(distance, case["expected_distance_m"])
                if "expected_traction_work_j" in case:
                    check_close(case["traction_force_n"] * distance, case["expected_traction_work_j"])
                if "expected_resistance_work_j" in case:
                    check_close(case["resistance_n"] * distance, case["expected_resistance_work_j"])
    return len(fixtures["cases"])


def save_csv(output, name, rows):
    if output is None:
        return
    with (output / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional directory for generated screening CSVs")
    args = parser.parse_args()
    ref = json.loads((ROOT / "data/reference/lrt2-2011.json").read_text(encoding="utf-8"))
    check_close(sum(ref["empty_car_masses_kg"]), ref["empty_train_mass_kg"])
    check_close(4.68 / 3.6, ref["acceleration_anchor_mps2"])
    fixture_count = check_fixtures()
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)

    mass0 = ref["empty_train_mass_kg"]
    vmax = ref["maximum_speed_mps"]
    acceleration = ref["acceleration_anchor_mps2"]
    rows = []
    for passengers in ref["load_scenarios_passengers"]:
        mass = mass0 + passengers * ref["passenger_mass_convention_kg"]
        for rotary_fraction in [0, 0.05, 0.10, 0.15]:
            effective = mass + rotary_fraction * mass0
            rows.append({
                "passengers": passengers,
                "actual_mass_kg": mass,
                "assumed_rotary_fraction_of_tare": rotary_fraction,
                "effective_mass_kg": effective,
                "force_for_anchor_acceleration_no_resistance_n": effective * acceleration,
                "power_for_anchor_acceleration_at_80kph_no_resistance_w": effective * acceleration * vmax,
                "kinetic_energy_at_80kph_kwh": effective * vmax**2 / 2 / 3.6e6,
                "potential_energy_10m_climb_kwh": mass * G * 10 / 3.6e6,
                "grade_force_1pct_n": mass * G * 0.01 / math.sqrt(1 + 0.01**2),
            })
    save_csv(args.output, "mass-inertia-preflight.csv", rows)

    nominal_mass = mass0 + 826 * ref["passenger_mass_convention_kg"]
    # A 10% tare rotary allowance and all wheel powers below are hypothetical stress cases.
    effective = nominal_mass + 0.10 * mass0
    power_rows = []
    for power in [1e6, 1.5e6, 2e6]:
        for speed_kph in [20, 40, 60, 80]:
            speed = speed_kph / 3.6
            force = power / speed
            power_rows.append({
                "assumed_wheel_power_w": power,
                "speed_kph": speed_kph,
                "constant_power_force_ceiling_n": force,
                "level_acceleration_ceiling_no_resistance_mps2": force / effective,
                "uphill_1pct_acceleration_ceiling_no_resistance_mps2":
                    (force - nominal_mass * G * 0.01 / math.sqrt(1 + 0.01**2)) / effective,
            })
    save_csv(args.output, "power-envelope-preflight.csv", power_rows)

    # Whole-train forces for unit/scale screening, not fitted Davis coefficients.
    coast_rows = []
    for resistance in [0, 5000, 10000]:
        for signed_grade in [-0.01, 0, 0.01]:
            gravity = nominal_mass * G * signed_grade / math.sqrt(1 + signed_grade**2)
            coast_rows.append({
                "assumed_resistance_n": resistance,
                "assumed_grade_fraction": signed_grade,
                "coasting_acceleration_mps2": (-resistance - gravity) / effective,
            })
    save_csv(args.output, "coasting-preflight.csv", coast_rows)

    required_power = effective * acceleration * vmax
    height_work = nominal_mass * G * 10 / 3.6e6
    ideal_stop = vmax**2 / (2 * ref["service_deceleration_anchor_mps2"])
    print(f"Reference arithmetic and {fixture_count} analytical fixtures passed.")
    print(f"Required wheel power for the conditional acceleration case: {required_power/1e6:.3f} MW")
    print(f"Hypothetical effective mass: {effective:,.0f} kg; 10 m climb: {height_work:.3f} kWh")
    print(f"Ideal constant-deceleration stop: {ideal_stop:.3f} m; excludes operational braking effects")
    print("Screening only: the 826-passenger scenario does not reproduce the published AW3 performance condition.")
    if args.output is not None:
        print(f"Wrote three screening CSVs to {args.output}")


if __name__ == "__main__":
    main()
