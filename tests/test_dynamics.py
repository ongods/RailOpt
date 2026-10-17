"""Verification against independent analytical results and physical invariants."""

import json
import math
import copy
from dataclasses import replace
from pathlib import Path
import unittest
import tempfile

import numpy as np

from railway.integration import Settings, energy_residual_j, integrate_segment
from railway.journey import Route, simulate_journey
from railway.physics import Command, G, InfeasibleRun, Vehicle, forces, slope_from_grade
from railway.run import load_scenario

ROOT = Path(__file__).resolve().parents[1]


def vehicle(**changes):
    values = dict(mass_kg=200000, rotating_mass_kg=10000, traction_force_n=220000,
                  wheel_power_w=1500000, service_brake_force_n=240000,
                  davis_a_n=4000, davis_b_ns_per_m=80, davis_c_ns2_per_m2=15)
    values.update(changes)
    return Vehicle(**values)


class AnalyticalTests(unittest.TestCase):
    def test_versioned_analytical_fixtures(self):
        cases = json.loads((ROOT / 'data/verification/analytical-fixtures.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['id']):
                train = vehicle(mass_kg=case['mass_kg'], rotating_mass_kg=case['rotating_mass_kg'],
                                traction_force_n=case.get('maximum_force_n', case.get('traction_force_n', 0)),
                                wheel_power_w=case.get('wheel_power_w', 1e9),
                                service_brake_force_n=case.get('brake_force_n', 0),
                                davis_a_n=case['resistance_n'], davis_b_ns_per_m=0, davis_c_ns2_per_m2=0)
                mode = 'brake' if case.get('brake_force_n', 0) else 'traction' if train.traction_force_n else 'coast'
                downhill = case['id'] == 'lossless-downhill-coast'
                slope = -0.01 if downhill else 0
                result = integrate_segment(train, Command(mode), initial_speed_mps=case['initial_speed_mps'],
                                           duration_s=case.get('duration_s', 100 if downhill else 40), dh_ds=slope,
                                           end_position_m=500 if downhill else None,
                                           settings=Settings(max_step_s=0.73))
                final = result.states[:, -1]
                for key, value in [('expected_speed_mps', final[1]), ('expected_distance_m', final[0]),
                                   ('expected_traction_work_j', final[2]), ('expected_brake_work_j', final[3]),
                                   ('expected_resistance_work_j', final[4]),
                                   ('expected_final_speed_squared_m2ps2', final[1]**2),
                                   ('expected_stop_time_s', result.time_s[-1]),
                                   ('expected_stop_distance_m', final[0])]:
                    if key in case:
                        self.assertAlmostEqual(value, case[key], delta=max(1e-6, abs(case[key]) * 1e-7))
                if 'expected_stop_time_s' in case:
                    self.assertEqual(result.termination, 'stopped')
                    self.assertLess(abs(final[1]), 1e-8)
                heights = result.states[0] * slope
                residual = energy_residual_j(train, result.states, heights, case['initial_speed_mps'])
                self.assertLess(np.max(np.abs(residual)), 0.1)
                self.assertGreaterEqual(result.states[1].min(), -1e-8)

    def test_zero_net_force_is_constant_speed(self):
        train = vehicle(davis_b_ns_per_m=0, davis_c_ns2_per_m2=0)
        result = integrate_segment(train, Command('cruise'), initial_speed_mps=12, duration_s=7.3)
        self.assertAlmostEqual(result.states[0, -1], 87.6, places=8)
        np.testing.assert_allclose(result.states[1], 12, atol=1e-9)

    def test_force_power_transition_from_rest(self):
        train = vehicle(rotating_mass_kg=0, traction_force_n=200000, wheel_power_w=1000000,
                        davis_a_n=0, davis_b_ns_per_m=0, davis_c_ns2_per_m2=0)
        result = integrate_segment(train, Command('traction'), initial_speed_mps=0, duration_s=10,
                                   settings=Settings(max_step_s=1.7))
        # 5 s at 1 m/s² then 5 s at 1 MW: v²=25+2*1e6*5/2e5=75.
        self.assertAlmostEqual(result.states[1, -1]**2, 75, places=5)
        self.assertAlmostEqual(result.states[2, -1], 7.5e6, delta=0.1)
        self.assertTrue(np.any(np.abs(result.states[1] - 5) < 1e-8))

    def test_stop_between_requested_steps(self):
        train = vehicle(mass_kg=200000, rotating_mass_kg=0, service_brake_force_n=180000,
                        davis_a_n=0, davis_b_ns_per_m=0, davis_c_ns2_per_m2=0)
        result = integrate_segment(train, Command('brake'), initial_speed_mps=2, duration_s=10,
                                   settings=Settings(max_step_s=0.7))
        self.assertAlmostEqual(result.time_s[-1], 2 / 0.9, places=7)
        self.assertAlmostEqual(result.states[0, -1], 4 / 1.8, places=7)
        self.assertLess(abs(result.states[1, -1]), 1e-8)

    def test_actual_mass_for_gravity_effective_mass_for_inertia(self):
        train = vehicle()
        grade = slope_from_grade(-0.02)
        force = forces(train, 10, grade, Command('coast'))
        expected = (-train.resistance_n(10) - train.mass_kg * G * grade) / train.effective_mass_kg
        self.assertAlmostEqual(force.acceleration_mps2, expected)
        self.assertGreater(force.acceleration_mps2, 0)
        self.assertAlmostEqual(grade, -0.02 / math.sqrt(1.0004))


class JourneyTests(unittest.TestCase):
    def assert_run(self, train, route, result):
        x, speed, wt, wb, wr = result.states
        self.assertTrue(np.isfinite(result.states).all())
        self.assertTrue(np.all(np.diff(result.time_s) > 0))
        self.assertTrue(np.all(np.diff(x) >= -1e-8))
        self.assertGreaterEqual(speed.min(), -1e-8)
        self.assertLess(abs(x[-1] - route.length_m), 0.5)
        self.assertLess(abs(speed[-1]), 0.05)
        for work in [wt, wb, wr]:
            self.assertTrue(np.all(np.diff(work) >= -1e-3))
        for i, (position, v, mode, slope) in enumerate(zip(x, speed, result.modes, result.slopes)):
            f = forces(train, max(float(v), 0), float(slope), Command(mode))
            self.assertLessEqual(f.traction_n, train.available_traction_n(max(float(v), 0)) + 1)
            self.assertLessEqual(f.brake_n, train.service_brake_force_n + 1)
            self.assertLessEqual(f.traction_n * v, train.wheel_power_w * 1.001)
            self.assertEqual(f.traction_n * f.brake_n, 0)
            self.assertLessEqual(v, route.speed_limit_mps(float(position)) + 0.05)
        scale = max(wt.max(), wb.max(), wr.max(), 1000)
        self.assertLess(np.max(np.abs(result.energy_residual_j)), 0.001 * scale)

    def test_station_journey_with_grade_coast_and_lower_speed_limit(self):
        train = vehicle()
        route = Route(((0, 0), (200, 0), (450, 2.5), (700, 2.5), (1000, 0)),
                      ((0, 20), (650, 12), (850, 16)))
        result = simulate_journey(train, route, coast_from_m=400)
        self.assert_run(train, route, result)
        self.assertEqual(set(result.modes), {'traction', 'cruise', 'coast', 'brake'})
        self.assertLess(abs(route.height_m(result.states[0, -1])), 0.01)

    def test_short_route_never_reaches_speed_cap(self):
        train = vehicle()
        route = Route(((0, 0), (30, 0)), ((0, 20),))
        result = simulate_journey(train, route)
        self.assert_run(train, route, result)
        self.assertLess(result.states[1].max(), 10)
        self.assertNotIn('cruise', result.modes)

    def test_initial_speed_too_high_to_stop(self):
        with self.assertRaises(InfeasibleRun):
            simulate_journey(vehicle(), Route(((0, 0), (10, 0)), ((0, 25),)), initial_speed_mps=20)

    def test_insufficient_traction_and_braking(self):
        route = Route(((0, 0), (1000, 50)), ((0, 20),))
        with self.assertRaises(InfeasibleRun):
            simulate_journey(vehicle(traction_force_n=10000), route)
        with self.assertRaises(InfeasibleRun):
            simulate_journey(vehicle(service_brake_force_n=10000),
                             Route(((0, 50), (1000, 0)), ((0, 20),)))

    def test_coast_can_stop_before_station(self):
        with self.assertRaises(InfeasibleRun):
            simulate_journey(vehicle(), Route(((0, 0), (1000, 0)), ((0, 20),)), coast_from_m=1)

    def test_time_limit_is_explicitly_rejected(self):
        with self.assertRaises(InfeasibleRun):
            simulate_journey(vehicle(), Route(((0, 0), (1000, 0)), ((0, 20),)), maximum_time_s=1)

    def test_refinement_and_determinism(self):
        train = vehicle()
        route = Route(((0, 0), (300, 3), (700, -1), (1000, 0)), ((0, 20), (650, 10)))
        base = Settings(max_step_s=0.5, planning_step_m=10, rtol=1e-8)
        coarse = simulate_journey(train, route, settings=base)
        fine = simulate_journey(train, route, settings=replace(base, max_step_s=0.25, planning_step_m=5, rtol=1e-10))
        again = simulate_journey(train, route, settings=base)
        self.assert_run(train, route, fine)
        np.testing.assert_array_equal(coarse.states, again.states)
        for a, b in zip([coarse.time_s[-1], *coarse.states[2:, -1]],
                        [fine.time_s[-1], *fine.states[2:, -1]]):
            self.assertLess(abs(a - b) / max(abs(b), 1000 if b > 1000 else 1), 0.005)

    def test_zero_net_height_still_changes_motion(self):
        train = vehicle()
        limits = ((0, 20),)
        flat = simulate_journey(train, Route(((0, 0), (1000, 0)), limits))
        hill = simulate_journey(train, Route(((0, 0), (500, 10), (1000, 0)), limits))
        self.assertGreater(abs(flat.time_s[-1] - hill.time_s[-1]), 0.01)

    def test_increasing_speed_limit_and_nonzero_initial_speed(self):
        train = vehicle()
        route = Route(((0, 0), (1000, 0)), ((0, 8), (300, 20), (800, 10)))
        result = simulate_journey(train, route, initial_speed_mps=5)
        self.assert_run(train, route, result)
        self.assertGreater(result.states[1].max(), 12)
        self.assertAlmostEqual(result.states[1, 0], 5)

    def test_uphill_cannot_hold_speed_but_can_complete_at_lower_speed(self):
        train = vehicle(wheel_power_w=250000)
        route = Route(((0, 0), (1000, 10)), ((0, 20),))
        result = simulate_journey(train, route, initial_speed_mps=20)
        self.assert_run(train, route, result)
        self.assertLess(result.states[1, len(result.time_s)//2], 20)


class InputTests(unittest.TestCase):
    def test_invalid_physical_inputs(self):
        for changes in [{'mass_kg': 0}, {'mass_kg': -1}, {'wheel_power_w': float('nan')},
                        {'davis_a_n': -1}, {'rotating_mass_kg': float('inf')}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                vehicle(**changes)
        for command in [('unknown', 1), ('traction', 1.1), ('brake', -1)]:
            with self.assertRaises(ValueError):
                Command(*command)
        with self.assertRaises(ValueError):
            Settings(max_step_s=0)
        with self.assertRaises(ValueError):
            Route(((0, 0), (0, 1)), ((0, 20),))
        with self.assertRaises(ValueError):
            Route(((0, 0), (100, 0)), ((0, 0),))

    def test_explicit_standstill_and_hold(self):
        train = vehicle()
        result = integrate_segment(train, Command('hold'), initial_speed_mps=0, duration_s=5, dh_ds=0.01)
        np.testing.assert_array_equal(result.states, np.zeros_like(result.states))
        self.assertEqual(result.time_s[-1], 5)
        with self.assertRaises(InfeasibleRun):
            integrate_segment(train, Command('coast'), initial_speed_mps=0, duration_s=1)
        with self.assertRaises(InfeasibleRun):
            integrate_segment(vehicle(service_brake_force_n=1), Command('hold'), initial_speed_mps=0,
                              duration_s=1, dh_ds=0.01)
        with self.assertRaises(InfeasibleRun):
            forces(vehicle(wheel_power_w=10000), 20, 0, Command('cruise'))

    def test_zero_power_and_partial_commands(self):
        powerless = vehicle(wheel_power_w=0)
        self.assertEqual(powerless.available_traction_n(0), 0)
        with self.assertRaises(InfeasibleRun):
            integrate_segment(powerless, Command('traction'), initial_speed_mps=0, duration_s=1)
        train = vehicle()
        f = forces(train, 10, 0, Command('traction', 0.5))
        self.assertAlmostEqual(f.traction_n, 0.5 * train.available_traction_n(10))
        self.assertEqual(f.brake_n, 0)
        with self.assertRaises(ValueError):
            forces(train, -1, 0, Command('coast'))
        with self.assertRaises(ValueError):
            forces(train, 1, 1, Command('coast'))

    def test_downhill_cruise_uses_braking(self):
        train = vehicle()
        f = forces(train, 10, -0.02, Command('cruise'))
        self.assertEqual(f.traction_n, 0)
        self.assertGreater(f.brake_n, 0)
        self.assertAlmostEqual(f.acceleration_mps2, 0)
        with self.assertRaises(InfeasibleRun):
            forces(vehicle(service_brake_force_n=1), 10, -0.02, Command('cruise'))

    def test_scenario_evidence_and_mass_consistency(self):
        original = json.loads((ROOT / 'data/scenarios/synthetic-1km.json').read_text())
        config, train, route, settings = load_scenario(ROOT / 'data/scenarios/synthetic-1km.json')
        self.assertEqual(train.mass_kg, 213790)
        for defect in ('missing_evidence', 'null_force', 'mass_mismatch', 'wrong_units'):
            invalid = copy.deepcopy(original)
            if defect == 'missing_evidence':
                del invalid['evidence']['wheel_power_w']
            elif defect == 'null_force':
                invalid['vehicle']['traction_force_n'] = None
            elif defect == 'mass_mismatch':
                invalid['mass_basis']['passengers'] += 1
            else:
                invalid['units'] = 'km/h and tonnes'
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'invalid.json'
                path.write_text(json.dumps(invalid), encoding='utf-8')
                with self.subTest(defect=defect), self.assertRaises(ValueError):
                    load_scenario(path)


if __name__ == '__main__':
    unittest.main()
