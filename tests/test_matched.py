"""Matched-arrival feasibility and independent verification, using small grids."""

import copy
import json
import unittest
from unittest.mock import patch

from railway.matched import compare, evaluate, report, robustness, validate_experiment, verify
from railway.run import ROOT, load_scenario


class MatchedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, cls.train, cls.route, cls.settings = load_scenario(ROOT / "data/scenarios/synthetic-1km.json")
        cls.spec = json.loads((ROOT / "data/experiments/matched-time.json").read_text())
        cls.spec.update(cruise_speed_caps_mps=[14, 18, 20], coast_positions_m=[300, 500], crossing_iterations=6,
                        search_energy_tolerance_j=1e6)
        cls.study, cls.runs = compare(cls.train, cls.route, cls.config, cls.settings, cls.spec)

    def test_pair_matches_time_and_physical_requirements(self):
        self.assertEqual(self.study["status"], "verified_comparison")
        for name in ("reference", "candidate"):
            case = self.study["refined_search"][name]
            self.assertLessEqual(abs(case["arrival_error_s"]), 0.1)
            self.assertTrue(case["audit"]["passed"])
            self.assertTrue(self.study["verification"][name]["passed"])
            self.assertEqual(self.runs[name].time_s[-1], case["summary"]["travel_time_s"])
        self.assertIsNone(self.study["refined_search"]["reference"]["control"]["coast_from_m"])
        self.assertTrue(self.study["search_resolution"]["passed"])

    def test_impossible_target_and_all_policy_rejections(self):
        spec = {**self.spec, "target_time_s": 1, "cruise_speed_caps_mps": [14, 20], "coast_positions_m": [0, 1]}
        study, runs = compare(self.train, self.route, self.config, self.settings, spec)
        self.assertEqual(study["status"], "no_feasible_comparison_within_tested_bounds")
        self.assertEqual(runs, {})
        self.assertIn("time_infeasible", study["refined_search"]["counts"])
        config = {**self.config, "control": {**self.config["control"], "maximum_time_s": 1}}
        study, _ = compare(self.train, self.route, config, self.settings, spec)
        self.assertEqual(set(study["refined_search"]["counts"]), {"infeasible_policy"})

    def test_audit_failure_and_numerical_failure_do_not_become_feasible(self):
        control = self.study["refined_search"]["reference"]["control"]
        with patch("railway.matched.audit_profile", return_value={"passed": False}):
            case, _ = evaluate(self.train, self.route, self.config, self.settings, self.spec, control)
            self.assertEqual(case["status"], "audit_failed")
        with patch("railway.journey.solve_ivp", side_effect=RuntimeError("broken solver")):
            with self.assertRaisesRegex(RuntimeError, "broken solver"):
                evaluate(self.train, self.route, self.config, self.settings, self.spec, control)

    def test_serialized_replay_determinism_and_refinement_arrival_requirement(self):
        case = self.study["refined_search"]["reference"]
        checks, _ = verify(self.train, self.route, self.config, self.settings, self.spec, case)
        self.assertEqual(checks, self.study["verification"]["reference"])
        missed = copy.deepcopy(checks["refined"])
        missed["status"] = "time_infeasible"
        with patch("railway.matched.evaluate", side_effect=[(checks["replay"], None), (missed, None)]):
            failed, _ = verify(self.train, self.route, self.config, self.settings, self.spec, case)
            self.assertFalse(failed["passed"])

    def test_fixed_control_robustness_uses_same_controls_and_time(self):
        spec = {**self.spec, "robustness": {"auxiliary_power_w": [50000], "regenerative_acceptance_fraction": [0, 1]}}
        result = robustness(self.train, self.route, self.config, self.settings, spec, self.study)
        self.assertEqual(len(result["cases"]), 2)
        for case in result["cases"]:
            for name, profile in case["pair"].items():
                self.assertEqual(profile["control"], self.study["refined_search"][name]["control"])
                self.assertEqual(profile["status"], "feasible")
                self.assertTrue(profile["verification"]["passed"])

    def test_invalid_search_choices(self):
        for change in ({"arrival_tolerance_s": 0}, {"target_time_s": float("nan")},
                       {"coast_positions_m": [0, 1000]}, {"cruise_speed_caps_mps": [0, 10]},
                       {"crossing_iterations": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_experiment({**self.spec, **change}, self.route)

    def test_pair_found_only_after_grid_refinement_is_not_reported_absent(self):
        coarse = copy.deepcopy(self.study["coarse_search"])
        coarse["candidate"] = None
        fine = self.study["refined_search"]
        with patch("railway.matched.search", side_effect=[coarse, fine]):
            study, runs = compare(self.train, self.route, self.config, self.settings, self.spec)
        self.assertEqual(study["status"], "verification_failed")
        self.assertEqual(set(runs), {"reference", "candidate"})
        self.assertFalse(study["search_resolution"]["passed"])
        self.assertIn("only after grid refinement", study["search_resolution"]["reason"])
        text = report({"experiment_id": "test", "experiment": self.spec, "comparison": study})
        self.assertIn("No verified comparison", text)
        self.assertNotIn("This is the best feasible tested profile", text)


if __name__ == "__main__":
    unittest.main()
