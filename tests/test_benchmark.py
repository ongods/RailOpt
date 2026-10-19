"""Coasting experiment checks: feasibility, dominance and reproducible artifacts."""

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET
import numpy as np

from railway.benchmark import audit_profile, classify_frontier, feasibility_report, run_benchmark, validate_experiment
from railway.journey import simulate_journey
from railway.run import electrical_parameters, load_scenario

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, cls.train, cls.route, cls.settings = load_scenario(ROOT / "data/scenarios/synthetic-1km.json")
        cls.specification = json.loads((ROOT / "data/experiments/coasting-benchmark.json").read_text())
        cls.specification["coast_positions_m"] = [0, 1, 25, 50, 75, 150, 350, 500, 750]
        cls.result = run_benchmark(cls.train, cls.route, cls.config, cls.settings, cls.specification)

    def test_policy_rejections_have_no_fabricated_time_or_energy(self):
        cases = {case["case_id"]: case for case in self.result["cases"]}
        self.assertEqual(self.result["counts"], {"feasible": 7, "infeasible_policy": 3})
        for name in ("coast_0m", "coast_1m", "coast_25m"):
            self.assertNotIn("summary", cases[name])
            self.assertTrue(cases[name]["reason"])
            self.assertFalse(cases[name]["on_sampled_frontier"])
        for case in self.result["cases"]:
            if case["status"] == "feasible":
                self.assertTrue(all(case["audit"]["checks"].values()))
                self.assertLessEqual(abs(case["summary"]["stop_error_m"]), 0.5)

    def test_actual_time_auxiliaries_and_tradeoff_are_preserved(self):
        cases = {case["case_id"]: case for case in self.result["cases"]}
        for case in self.result["cases"]:
            if case["status"] == "feasible":
                summary = case["summary"]
                expected = summary["wheel_traction_work_j"] / 0.85 + 100000 * summary["travel_time_s"]
                self.assertAlmostEqual(summary["electrical"]["net_supply_energy_j"], expected, delta=0.001)
        slow = cases["coast_50m"]["summary"]
        faster = cases["coast_75m"]["summary"]
        self.assertGreater(slow["travel_time_s"], faster["travel_time_s"])
        self.assertGreater(slow["electrical"]["net_supply_energy_j"], faster["electrical"]["net_supply_energy_j"])
        self.assertIn("coast_75m", cases["coast_50m"]["dominated_by"])
        self.assertEqual(self.config["control"]["coast_from_m"], 500)
        self.assertTrue(cases["coast_500m"]["scenario_control"])

    def test_refinement_retains_feasibility_and_energy(self):
        selected = {case["case_id"]: case for case in self.result["cases"] if "refinement" in case}
        for name in ("no_coast", "coast_25m", "coast_50m", "coast_75m", "coast_500m"):
            self.assertIn(name, selected)
        for case in selected.values():
            self.assertTrue(case["refinement"]["passed"], case["case_id"])
            if case["status"] == "feasible":
                self.assertTrue(case["refinement"]["audit"]["passed"])
                self.assertLess(max(case["refinement"]["relative_changes"].values()), 0.005)

    def test_independent_audit_detects_terminal_state_corruption(self):
        result = simulate_journey(self.train, self.route, electrical=electrical_parameters(self.config),
                                  settings=self.settings, **self.config["control"])
        result.states[0, -1] -= 5
        audit = audit_profile(self.train, self.route, self.settings, result, electrical_parameters(self.config))
        self.assertFalse(audit["passed"])
        self.assertFalse(audit["checks"]["station_stop"])

    def test_frontier_ties_dominance_and_rejected_points(self):
        def case(name, time, energy):
            return {"case_id": name, "status": "feasible",
                    "summary": {"travel_time_s": time, "electrical": {"net_supply_energy_j": energy}}}
        cases = [case("fast", 10, 1000), case("duplicate", 10.001, 1000.1),
                 case("worse", 11, 1100), case("economical", 12, 900),
                 {"case_id": "rejected", "status": "infeasible_policy"}]
        classify_frontier(cases, 0.01, 1)
        self.assertTrue(cases[0]["on_sampled_frontier"])
        self.assertTrue(cases[1]["on_sampled_frontier"])
        self.assertIn("fast", cases[2]["dominated_by"])
        self.assertTrue(cases[3]["on_sampled_frontier"])
        self.assertFalse(cases[4]["on_sampled_frontier"])

    def test_invalid_design_and_missing_electrical_model_are_rejected(self):
        for positions in ([], [-1], [1000], [1, 1], [2, 1], [float("nan")]):
            specification = copy.deepcopy(self.specification)
            specification["coast_positions_m"] = positions
            with self.subTest(positions=positions), self.assertRaises(ValueError):
                validate_experiment(specification, self.route)
        specification = copy.deepcopy(self.specification)
        specification["dominance_tolerances"]["time_s"] = -1
        with self.assertRaises(ValueError):
            validate_experiment(specification, self.route)
        config = copy.deepcopy(self.config)
        del config["electrical"]
        with self.assertRaises(ValueError):
            run_benchmark(self.train, self.route, config, self.settings, self.specification)

    def test_software_failure_is_not_classified_as_policy_infeasibility(self):
        with patch("railway.benchmark.simulate_journey", side_effect=RuntimeError("integration failed")):
            with self.assertRaisesRegex(RuntimeError, "integration failed"):
                run_benchmark(self.train, self.route, self.config, self.settings, self.specification)

    def test_spatial_solver_failures_propagate_through_benchmark(self):
        for success, states, times in ((False, [[0.0]], [0]), (True, [[float("nan")]], [0]),
                                       (True, [[0.0]], [float("nan")])):
            failed = SimpleNamespace(success=success, y=np.array(states), t=np.array(times), message="injected spatial failure")
            with self.subTest(success=success), patch("railway.journey.solve_ivp", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "Spatial planning failed"):
                    run_benchmark(self.train, self.route, self.config, self.settings, self.specification)

    def test_all_rejected_sweep_has_no_frontier_and_keeps_reasons(self):
        config = copy.deepcopy(self.config)
        config["control"]["maximum_time_s"] = 1
        config["control"]["coast_from_m"] = None
        specification = copy.deepcopy(self.specification)
        specification["coast_positions_m"] = [0, 1]
        specification["refine_coast_positions_m"] = []
        result = run_benchmark(self.train, self.route, config, self.settings, specification)
        self.assertEqual(result["counts"], {"infeasible_policy": 3})
        self.assertEqual(result["sampled_frontier_ids"], [])
        record = {"benchmark_id": "test", "configuration": config, "experiment": specification, **result}
        report = feasibility_report(record)
        for case in result["cases"]:
            self.assertIn(case["reason"], report)
        self.assertIn("infeasible_policy", report)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Install requirements.txt for plot/export checks")
    def test_cli_exports_plot_evidence_and_rejects_overwrite(self):
        specification = copy.deepcopy(self.specification)
        specification["coast_positions_m"] = [0, 50, 500]
        specification["refine_coast_positions_m"] = []
        with tempfile.TemporaryDirectory() as directory:
            experiment = Path(directory) / "experiment.json"
            experiment.write_text(json.dumps(specification), encoding="utf-8")
            output = Path(directory) / "output"
            command = [sys.executable, "-m", "railway.benchmark", "--experiment", str(experiment), "--output", str(output)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((output / "benchmark.json").read_text())
            self.assertEqual(record["counts"], {"feasible": 3, "infeasible_policy": 1})
            for name, digest in record["code_sha256"].items():
                self.assertEqual(hashlib.sha256((ROOT / "railway" / name).read_bytes()).hexdigest(), digest)
            self.assertEqual((output / "energy-time.png").read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            svg = ET.parse(output / "energy-time.svg")
            svg_text = " ".join(svg.getroot().itertext())
            self.assertIn("Journey time (s)", svg_text)
            self.assertIn("Net train-terminal energy (kWh)", svg_text)
            self.assertIn(record["benchmark_id"], (output / "coasting-feasibility.md").read_text(encoding="utf-8"))
            with (output / "profiles.csv").open(newline="") as stream:
                rows = {row["case_id"]: row for row in csv.DictReader(stream)}
            self.assertEqual(rows["coast_0m"]["net_supply_energy_j"], "")
            no_coast = next(case for case in record["cases"] if case["case_id"] == "no_coast")
            self.assertAlmostEqual(float(rows["no_coast"]["net_supply_energy_j"]),
                                   no_coast["summary"]["electrical"]["net_supply_energy_j"])
            saved = (output / "benchmark.json").read_bytes()
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("already exist", completed.stderr)
            self.assertEqual((output / "benchmark.json").read_bytes(), saved)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Install requirements.txt for plot checks")
    def test_plot_handles_no_feasible_profiles(self):
        from railway.plotting import plot_energy_time
        with tempfile.TemporaryDirectory() as directory:
            record = {"benchmark_id": "no-feasible-fixture", "cases": [
                {"case_id": "rejected", "status": "infeasible_policy"}]}
            plot_energy_time(record, Path(directory))
            svg = ET.parse(Path(directory) / "energy-time.svg")
            self.assertIn("No feasible profiles", " ".join(svg.getroot().itertext()))


if __name__ == "__main__":
    unittest.main()
