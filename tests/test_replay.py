"""Saved-run integrity and playback checks, independent of any GUI event loop."""

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from railway.journey import simulate_journey
from railway.replay import PlaybackClock, load_run
from railway.run import ROOT, electrical_parameters, export_run, load_scenario


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, cls.train, cls.route, cls.settings = load_scenario(ROOT / "data/scenarios/synthetic-1km.json")
        cls.result = simulate_journey(cls.train, cls.route, settings=cls.settings,
                                      electrical=electrical_parameters(cls.config), **cls.config["control"])

    def save(self, directory):
        return export_run(self.config, self.train, self.route, self.settings, self.result, directory)

    def alter_csv(self, directory, mutate):
        path = Path(directory) / "trajectory.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        mutate(fields, rows)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        record_path = Path(directory) / "run.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["trajectory_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        record_path.write_text(json.dumps(record), encoding="utf-8")

    def test_endpoints_bounded_motion_energy_and_one_sided_switches(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.save(directory)
            run = load_run(directory)
            self.assertEqual(run.sample(-10)["position_m"], 0)
            self.assertAlmostEqual(run.sample(1e9)["position_m"], self.route.length_m, delta=0.5)
            self.assertEqual(run.sample(1e9)["net_supply_energy_j"], record["summary"]["electrical"]["net_supply_energy_j"])
            for at in np.linspace(0, run.duration_s, 501):
                self.assertTrue(-1e-7 <= run.sample(at)["position_m"] <= self.route.length_m + 0.5)
            for phase in record["phases"][1:]:
                index = int(np.argmin(abs(run.columns["position_m"] - phase["start_m"])))
                at = run.columns["time_s"][index]
                self.assertEqual(run.sample(at)["mode"], phase["command"]["mode"])
                self.assertEqual(run.sample(at - 1e-8)["mode"], run.columns["mode"][index - 1])
                mid = (run.columns["time_s"][index - 1] + at) / 2
                self.assertEqual(run.sample(mid)["wheel_traction_power_w"], run.columns["wheel_traction_power_w"][index - 1])

    def test_playback_rate_pause_restart_and_final_freeze_do_not_change_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.save(directory)
            original = (Path(directory) / "trajectory.csv").read_bytes()
            run = load_run(directory)
            totals = []
            for rate in (0.25, 1, 8):
                clock = PlaybackClock(run.duration_s, speed=rate)
                self.assertEqual(clock.advance(10), 0)
                clock.paused = False
                for _ in range(int(run.duration_s / rate) + 2):
                    clock.advance(1)
                self.assertEqual(clock.time_s, run.duration_s)
                self.assertTrue(clock.paused)
                before = run.sample(clock.time_s)
                clock.advance(1000)
                self.assertEqual(before, run.sample(clock.time_s))
                totals.append(before["net_supply_energy_j"])
                clock.seek(0)
                self.assertEqual(clock.time_s, 0)
            self.assertEqual(len(set(totals)), 1)
            self.assertEqual((Path(directory) / "trajectory.csv").read_bytes(), original)
            for rate in (0, -1, float("nan")):
                with self.assertRaises(ValueError):
                    PlaybackClock(10, speed=rate)

    def test_hash_provenance_and_final_account_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            self.save(directory)
            path = Path(directory) / "trajectory.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                load_run(directory)
        with tempfile.TemporaryDirectory() as directory:
            self.save(directory)
            path = Path(directory) / "run.json"
            record = json.loads(path.read_text())
            record["configuration"]["control"]["coast_from_m"] += 10
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "provenance"):
                load_run(directory)
        with tempfile.TemporaryDirectory() as directory:
            self.save(directory)
            self.alter_csv(directory, lambda fields, rows: rows[-1].update(net_supply_energy_j="1"))
            with self.assertRaisesRegex(ValueError, "Final trajectory"):
                load_run(directory)

    def test_missing_invalid_columns_and_event_corruption(self):
        def missing(fields, rows):
            fields.remove("speed_mps")
            for row in rows:
                del row["speed_mps"]
        changes = [missing, lambda fields, rows: rows[1].update(speed_mps="nan"),
                   lambda fields, rows: rows[1].update(time_s="0"),
                   lambda fields, rows: rows[1].update(mode="brake")]
        for mutate in changes:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                self.save(directory)
                self.alter_csv(directory, mutate)
                with self.assertRaises(ValueError):
                    load_run(directory)

    def test_capped_scenario_round_trip_and_audit(self):
        from railway.benchmark import audit_profile
        with tempfile.TemporaryDirectory() as directory:
            config = {**self.config, "control": {**self.config["control"], "cruise_speed_cap_mps": 15, "coast_from_m": None}}
            path = Path(directory) / "scenario.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded, train, route, settings = load_scenario(path)
            result = simulate_journey(train, route, settings=settings, electrical=electrical_parameters(loaded), **loaded["control"])
            export_run(loaded, train, route, settings, result, Path(directory) / "run")
            saved = load_run(Path(directory) / "run")
            self.assertEqual(saved.record["configuration"]["control"]["cruise_speed_cap_mps"], 15)
            result.states[1, 5] = 16
            audit = audit_profile(train, route, settings, result, electrical_parameters(loaded), 15)
            self.assertFalse(audit["checks"]["commanded_speed_ceiling"])

    def test_sample_arbitrarily_close_before_phase_switch_keeps_old_mode(self):
        def insert_pre_event(fields, rows):
            index = next(i for i in range(1, len(rows)) if rows[i]["mode"] != rows[i-1]["mode"])
            left, right = rows[index-1], rows[index]
            gap = float(right["position_m"]) - float(left["position_m"])
            fraction = 1 - 5e-7 / gap
            added = {key: (left[key] if key == "mode" else
                           str(float(left[key]) + fraction * (float(right[key]) - float(left[key]))))
                     for key in fields}
            rows.insert(index, added)

        with tempfile.TemporaryDirectory() as directory:
            self.save(directory)
            self.alter_csv(directory, insert_pre_event)
            run = load_run(directory)
            index = next(i for i in range(1, len(run.columns["mode"]))
                         if run.columns["mode"][i] != run.columns["mode"][i-1])
            self.assertLess(run.columns["position_m"][index] - run.columns["position_m"][index-1], 1e-6)
            self.assertEqual(run.sample(run.columns["time_s"][index-1])["mode"], run.columns["mode"][index-1])

    def test_ragged_csv_rows_are_rejected(self):
        for extra in (True, False):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                self.save(directory)
                path = Path(directory) / "trajectory.csv"
                lines = path.read_text(encoding="utf-8").splitlines()
                lines[1] = lines[1] + ",123" if extra else lines[1].rsplit(",", 1)[0]
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                metadata = Path(directory) / "run.json"
                record = json.loads(metadata.read_text(encoding="utf-8"))
                record["trajectory_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                metadata.write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "column count"):
                    load_run(directory)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Install requirements.txt for viewer checks")
    def test_paired_snapshot_cli_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            self.save(first)
            self.save(second)
            image = Path(directory) / "pair.png"
            command = [sys.executable, "-m", "railway.replay", str(first), "--pair", str(second), "--snapshot", str(image)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            saved = image.read_bytes()
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(image.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
