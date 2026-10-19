"""Independent conversion, brake-blending and train-terminal balance cases."""

import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from railway.electrical import ElectricalParameters, electrical_energy, regenerative_powers
from railway.integration import Settings, integrate_segment
from railway.journey import Route, simulate_journey
from railway.physics import Command, Vehicle
from railway.run import convergence, electrical_sensitivity_cases, load_scenario, sensitivity, summary

ROOT = Path(__file__).resolve().parents[1]


def parameters(**changes):
    values = dict(motoring_efficiency=0.8, regenerative_efficiency=0.5,
                  auxiliary_power_w=1000, regenerative_force_n=5000,
                  regenerative_wheel_power_w=1e9, regenerative_acceptance_fraction=1,
                  maximum_export_power_w=1e9)
    values.update(changes)
    return ElectricalParameters(**values)


def train():
    return Vehicle(mass_kg=10000, rotating_mass_kg=0, traction_force_n=10000,
                   wheel_power_w=1e9, service_brake_force_n=10000,
                   davis_a_n=0, davis_b_ns_per_m=0, davis_c_ns2_per_m2=0)


def segment_energy(segment, electrical):
    return electrical_energy(electrical, segment.time_s - segment.time_s[0],
                             segment.states[2], segment.states[3], segment.electrical_integrals_j)


class ElectricalTests(unittest.TestCase):
    def brake(self, electrical, settings=Settings()):
        segment = integrate_segment(train(), Command("brake"), initial_speed_mps=20,
                                    duration_s=30, settings=settings, electrical=electrical)
        return segment, segment_energy(segment, electrical)

    def assert_accounts(self, segment, energy, electrical):
        # The stopped-event RHS extension has sub-joule quadrature error; the
        # existing mechanical analytical fixtures use a 0.1 J balance bound.
        tolerance = 0.1
        for name, values in vars(energy).items():
            self.assertTrue(np.isfinite(values).all(), name)
            if name not in {"net_supply_energy_j", "electrical_balance_residual_j"}:
                self.assertGreaterEqual(values.min(), -tolerance, name)
                self.assertGreaterEqual(np.diff(values).min(), -tolerance, name)
        self.assertTrue(np.all(energy.regenerative_wheel_work_j <= segment.states[3] + tolerance))
        self.assertTrue(np.all(energy.regenerative_accepted_energy_j <=
                               electrical.regenerative_acceptance_fraction *
                               energy.regenerative_potential_energy_j + tolerance))
        self.assertTrue(np.all(energy.auxiliary_reused_energy_j <= energy.auxiliary_energy_j + tolerance))
        elapsed = segment.time_s - segment.time_s[0]
        self.assertTrue(np.all(energy.supply_export_energy_j <=
                               electrical.maximum_export_power_w * elapsed + tolerance))
        np.testing.assert_allclose(energy.regenerative_generated_energy_j,
                                   energy.auxiliary_reused_energy_j + energy.supply_export_energy_j,
                                   atol=tolerance, rtol=0)
        # Independent train boundary: supply + initial kinetic = final kinetic + losses.
        delta_k = 0.5 * train().effective_mass_kg * (segment.states[1]**2 - segment.states[1, 0]**2)
        losses = (energy.motoring_loss_j + energy.regenerative_loss_j +
                  energy.friction_brake_work_j + energy.auxiliary_energy_j)
        np.testing.assert_allclose(energy.net_supply_energy_j, delta_k + losses, atol=tolerance, rtol=0)

    def test_motoring_conversion_and_auxiliaries(self):
        electrical = parameters()
        segment = integrate_segment(train(), Command("traction"), initial_speed_mps=0,
                                    initial_time_s=7, duration_s=10, electrical=electrical)
        energy = segment_energy(segment, electrical)
        self.assertAlmostEqual(energy.motoring_energy_j[-1], 625_000, delta=0.001)
        self.assertAlmostEqual(energy.motoring_loss_j[-1], 125_000, delta=0.001)
        self.assertAlmostEqual(energy.supply_import_energy_j[-1], 635_000, delta=0.001)
        self.assert_accounts(segment, energy, electrical)

    def test_holding_consumes_auxiliaries_without_wheel_work(self):
        electrical = parameters()
        segment = integrate_segment(train(), Command("hold"), initial_speed_mps=0,
                                    duration_s=5, electrical=electrical)
        energy = segment_energy(segment, electrical)
        self.assertEqual(energy.net_supply_energy_j[-1], 5000)
        self.assertEqual(energy.regenerative_accepted_energy_j[-1], 0)
        np.testing.assert_array_equal(segment.states, np.zeros_like(segment.states))

    def test_force_limited_recovery_and_auxiliary_reuse(self):
        electrical = parameters()
        segment, energy = self.brake(electrical)
        self.assertAlmostEqual(energy.regenerative_wheel_work_j[-1], 1_000_000, delta=0.01)
        self.assertAlmostEqual(energy.regenerative_generated_energy_j[-1], 500_000, delta=0.01)
        self.assertAlmostEqual(energy.friction_brake_work_j[-1], 1_000_000, delta=0.01)
        # Reuse is 1 kW for 19.6 s, then a 0.4 s triangular tail to zero.
        self.assertAlmostEqual(energy.auxiliary_reused_energy_j[-1], 19_800, delta=0.05)
        self.assertAlmostEqual(energy.supply_export_energy_j[-1], 480_200, delta=0.05)
        self.assertAlmostEqual(energy.supply_import_energy_j[-1], 200, delta=0.05)
        self.assert_accounts(segment, energy, electrical)

    def test_wheel_power_limit_and_transition(self):
        electrical = parameters(regenerative_force_n=10000, regenerative_wheel_power_w=50000,
                                auxiliary_power_w=0)
        segment, energy = self.brake(electrical)
        # 50 kW for 15 s, then force-limited slowing from 5 m/s to rest.
        self.assertAlmostEqual(energy.regenerative_wheel_work_j[-1], 875_000, delta=0.05)
        self.assertAlmostEqual(energy.supply_export_energy_j[-1], 437_500, delta=0.05)
        self.assert_accounts(segment, energy, electrical)

    def test_zero_acceptance_or_capability_uses_friction(self):
        cases = [dict(regenerative_acceptance_fraction=0), dict(regenerative_efficiency=0),
                 dict(regenerative_force_n=0), dict(regenerative_wheel_power_w=0),
                 dict(auxiliary_power_w=0, maximum_export_power_w=0)]
        for changes in cases:
            with self.subTest(changes=changes):
                electrical = parameters(**changes)
                segment, energy = self.brake(electrical)
                self.assertEqual(energy.regenerative_accepted_energy_j[-1], 0)
                self.assertAlmostEqual(energy.friction_brake_work_j[-1], 2_000_000, delta=0.1)
                self.assertAlmostEqual(energy.supply_import_energy_j[-1],
                                       20 * electrical.auxiliary_power_w, delta=0.01)
                self.assert_accounts(segment, energy, electrical)

    def test_partial_acceptance_and_export_cap(self):
        cases = [(parameters(auxiliary_power_w=0, regenerative_acceptance_fraction=0.4), 200_000),
                 (parameters(auxiliary_power_w=0, regenerative_force_n=10000,
                             maximum_export_power_w=10000), 190_000)]
        for electrical, expected in cases:
            with self.subTest(electrical=electrical):
                segment, energy = self.brake(electrical)
                self.assertAlmostEqual(energy.supply_export_energy_j[-1], expected, delta=0.05)
                self.assert_accounts(segment, energy, electrical)

    def test_local_reuse_without_export(self):
        electrical = parameters(regenerative_force_n=10000, maximum_export_power_w=0)
        segment, energy = self.brake(electrical)
        self.assertAlmostEqual(energy.auxiliary_reused_energy_j[-1], 19_900, delta=0.05)
        self.assertAlmostEqual(energy.net_supply_energy_j[-1], 100, delta=0.05)
        self.assertEqual(energy.supply_export_energy_j[-1], 0)
        self.assert_accounts(segment, energy, electrical)

    def test_ideal_full_recovery(self):
        electrical = parameters(regenerative_force_n=10000, regenerative_efficiency=1,
                                auxiliary_power_w=0, motoring_efficiency=1)
        segment, energy = self.brake(electrical)
        self.assertAlmostEqual(energy.supply_export_energy_j[-1], 2_000_000, delta=0.1)
        np.testing.assert_allclose(energy.friction_brake_work_j, 0, atol=0.001)
        np.testing.assert_allclose(energy.regenerative_loss_j, 0, atol=0.001)
        self.assert_accounts(segment, energy, electrical)

    def test_downhill_cruise_recovers_actual_brake_work(self):
        electrical = parameters(regenerative_force_n=10000, auxiliary_power_w=0)
        slope = -0.02
        segment = integrate_segment(train(), Command("cruise"), initial_speed_mps=10,
                                    duration_s=10, dh_ds=slope, electrical=electrical)
        energy = segment_energy(segment, electrical)
        expected_brake_work = 10000 * 9.80665 * 0.02 * 100
        self.assertAlmostEqual(energy.supply_export_energy_j[-1], 0.5 * expected_brake_work, delta=0.01)
        np.testing.assert_allclose(segment.states[1], 10, atol=1e-9)
        np.testing.assert_allclose(energy.friction_brake_work_j, 0, atol=0.001)

    def test_parameter_and_power_bounds(self):
        for field in ElectricalParameters.__dataclass_fields__:
            for value in (-1, float("nan"), float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    parameters(**{field: value})
        for field in ("motoring_efficiency", "regenerative_efficiency", "regenerative_acceptance_fraction"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                parameters(**{field: 1.01})
        with self.assertRaises(ValueError):
            parameters(motoring_efficiency=0)
        electrical = parameters(regenerative_wheel_power_w=20000, maximum_export_power_w=1000)
        for speed in (0, 0.01, 1, 10, 30):
            powers = regenerative_powers(electrical, 10000, speed)
            self.assertLessEqual(powers.wheel_power_w, min(10000 * speed, 5000 * speed, 20000))
            generated = electrical.regenerative_efficiency * powers.wheel_power_w
            self.assertLessEqual(generated - powers.auxiliary_reuse_w, 1000)

    def test_nonphysical_integrated_accounts_are_rejected(self):
        elapsed = np.array([0.0, 1.0])
        zero = np.zeros(2)
        # Recovery without wheel braking, or reuse without any generation.
        for integrals in (np.array([[0, 10000], [0, 10000], [0, 0]]),
                          np.array([[0, 0], [0, 0], [0, 10000]])):
            with self.subTest(integrals=integrals.tolist()), self.assertRaises(RuntimeError):
                electrical_energy(parameters(), elapsed, zero, zero, integrals)

    def test_journey_balance_continuity_and_mechanics_only_compatibility(self):
        route = Route(((0, 0), (100, 1), (300, 0)), ((0, 15),))
        electrical = parameters()
        result = simulate_journey(train(), route, electrical=electrical)
        legacy = simulate_journey(train(), route)
        self.assertIsNone(legacy.electrical)
        self.assertEqual(result.states.shape[0], 5)
        self.assertAlmostEqual(result.time_s[-1], legacy.time_s[-1], delta=1e-5)
        np.testing.assert_allclose(result.states[:, -1], legacy.states[:, -1], atol=0.01, rtol=0)
        energy = result.electrical
        np.testing.assert_allclose(energy.motoring_energy_j, result.states[2] / 0.8, atol=0.001)
        # Rest-to-rest, equal rail heights: terminal supply equals all modeled losses.
        losses = (energy.motoring_loss_j[-1] + energy.regenerative_loss_j[-1] +
                  energy.friction_brake_work_j[-1] + energy.auxiliary_energy_j[-1] + result.states[4, -1])
        self.assertAlmostEqual(energy.net_supply_energy_j[-1], losses, delta=0.01)
        self.assertEqual(len(energy.net_supply_energy_j), len(result.time_s))
        for name, values in vars(energy).items():
            if name not in {"net_supply_energy_j", "electrical_balance_residual_j"}:
                self.assertGreaterEqual(np.diff(values).min(), -0.001, name)
        self.assertIn("electrical", summary(train(), route, result))
        self.assertNotIn("electrical", summary(train(), route, legacy))

    def test_electrical_refinement_with_active_limits(self):
        config, vehicle, route, settings = load_scenario(ROOT / "data/scenarios/synthetic-1km.json")
        config["electrical"]["regenerative_acceptance_fraction"] = 0.6
        config["electrical"]["maximum_export_power_w"] = 50000
        electrical = ElectricalParameters(**config["electrical"])
        result = simulate_journey(vehicle, route, settings=settings, electrical=electrical, **config["control"])
        comparison = convergence(vehicle, route, config, settings, result)
        self.assertLess(max(comparison["relative_changes"].values()), 0.005)
        self.assertIn("electrical.supply_export_energy_j", comparison["relative_changes"])

    def test_scenario_evidence_and_optional_electrical_section(self):
        original = json.loads((ROOT / "data/scenarios/synthetic-1km.json").read_text())
        cases = []
        for defect in ("missing_evidence", "null_parameter", "invalid_efficiency"):
            config = copy.deepcopy(original)
            if defect == "missing_evidence":
                del config["evidence"]["auxiliary_power_w"]
            elif defect == "null_parameter":
                config["electrical"]["auxiliary_power_w"] = None
            else:
                config["electrical"]["motoring_efficiency"] = 0
            cases.append((defect, config))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.json"
            for defect, config in cases:
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(defect=defect), self.assertRaises(ValueError):
                    load_scenario(path)
            del original["electrical"]
            del original["sensitivity"]
            path.write_text(json.dumps(original), encoding="utf-8")
            config, _, _, _ = load_scenario(path)
            self.assertNotIn("electrical", config)

    def test_cli_exports_matching_electrical_accounts_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run([sys.executable, "-m", "railway.run", "--output", directory,
                                        "--convergence"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((Path(directory) / "run.json").read_text())
            with (Path(directory) / "trajectory.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            final = rows[-1]
            self.assertEqual(record["configuration"]["electrical"]["regenerative_acceptance_fraction"], 0)
            self.assertIn("electrical.py", record["code_sha256"])
            for name in ("net_supply_energy_j", "friction_brake_work_j", "regenerative_potential_energy_j"):
                self.assertAlmostEqual(float(final[name]), record["summary"]["electrical"][name])
            self.assertEqual(float(final["regenerative_accepted_energy_j"]), 0)
            self.assertGreater(float(final["regenerative_potential_energy_j"]), 0)
            config = record["configuration"]
            del config["electrical"]
            del config["sensitivity"]
            scenario = Path(directory) / "mechanics-only.json"
            scenario.write_text(json.dumps(config), encoding="utf-8")
            legacy_output = Path(directory) / "mechanics-only"
            completed = subprocess.run([sys.executable, "-m", "railway.run", "--scenario", str(scenario),
                                        "--output", str(legacy_output)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with (legacy_output / "trajectory.csv").open(newline="") as stream:
                self.assertNotIn("net_supply_energy_j", next(csv.reader(stream)))

    def test_sensitivity_preserves_trip_and_resolves_masked_parameters(self):
        config, vehicle, route, settings = load_scenario(ROOT / "data/scenarios/synthetic-1km.json")
        cases = sensitivity(vehicle, route, config, settings)
        indexed = {case["case"]: case for case in cases}
        self.assertEqual(len(cases), 36)
        baseline = indexed["baseline"]
        for case in cases:
            self.assertNotEqual(case["status"], "infeasible")
            self.assertIn("electrical_parameters", case)
            if case["category"] == "electrical":
                self.assertAlmostEqual(case["travel_time_s"], baseline["travel_time_s"], delta=1e-6)
                self.assertAlmostEqual(case["wheel_traction_work_j"], baseline["wheel_traction_work_j"], delta=0.1)
                reference = indexed[case["reference_case"]]
                self.assertLessEqual(len(case["changed_electrical_parameters"]), 1)
                self.assertAlmostEqual(case["net_supply_energy_change_j"],
                                       case["electrical"]["net_supply_energy_j"] -
                                       reference["electrical"]["net_supply_energy_j"])
        # Independent consequences at constant mechanical work and journey time.
        for efficiency in (0.75, 0.85, 0.95):
            case = indexed[f"electrical.motoring_efficiency={efficiency}"]
            expected = baseline["wheel_traction_work_j"] / efficiency + 100000 * baseline["travel_time_s"]
            self.assertAlmostEqual(case["electrical"]["net_supply_energy_j"], expected, delta=0.1)
        low_aux = indexed["electrical.auxiliary_power_w=50000"]
        high_aux = indexed["electrical.auxiliary_power_w=150000"]
        difference = high_aux["electrical"]["net_supply_energy_j"] - low_aux["electrical"]["net_supply_energy_j"]
        self.assertAlmostEqual(difference, 100000 * baseline["travel_time_s"], delta=0.1)
        self.assertEqual(indexed["regenerative.regenerative_efficiency=0.5"]["reference_case"], "regeneration_reference")
        self.assertGreater(indexed["regenerative.regenerative_efficiency=0.9"]["electrical"]["regenerative_accepted_energy_j"],
                           indexed["regenerative.regenerative_efficiency=0.5"]["electrical"]["regenerative_accepted_energy_j"])
        self.assertAlmostEqual(indexed["regenerative.maximum_export_power_w=0"]["electrical"]["supply_export_energy_j"], 0, delta=1e-6)
        self.assertGreater(indexed["regenerative.maximum_export_power_w=0"]["electrical"]["auxiliary_reused_energy_j"], 0)

    def test_sensitivity_ranges_are_validated_and_optional(self):
        original = json.loads((ROOT / "data/scenarios/synthetic-1km.json").read_text())
        for values in ([-0.1], [1.1], [float("nan")], []):
            config = copy.deepcopy(original)
            config["sensitivity"]["electrical"]["motoring_efficiency"] = values
            with self.subTest(values=values), self.assertRaises(ValueError):
                electrical_sensitivity_cases(config)
        config = copy.deepcopy(original)
        config["sensitivity"]["electrical"]["unknown_parameter"] = [1]
        with self.assertRaises(ValueError):
            electrical_sensitivity_cases(config)
        config = copy.deepcopy(original)
        del config["sensitivity"]
        self.assertEqual(electrical_sensitivity_cases(config), [])


if __name__ == "__main__":
    unittest.main()
