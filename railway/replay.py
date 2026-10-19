"""Schematic local viewer of saved simulation outputs; never runs the solver.

python -m railway.replay results/matched-time/reference --pair results/matched-time/candidate
"""

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

from .journey import Route
from .physics import finite


# Forces/powers and modes are right-continuous, held from the left sample.
# This avoids interpolating the incoming phase's force toward a switch's new force.
PIECEWISE = {"mode", "acceleration_mps2", "traction_force_n", "brake_force_n", "resistance_n",
             "grade_force_n", "wheel_traction_power_w", "regenerative_accepted_power_w"}
REQUIRED = {"time_s", "position_m", "speed_mps", "height_m", "mode", "wheel_traction_power_w",
            "wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j"}


@dataclass(frozen=True)
class SavedRun:
    record: dict
    columns: dict
    route: Route

    @property
    def duration_s(self):
        return float(self.columns["time_s"][-1])

    def sample(self, time_s):
        """Clamp display time; linearly interpolate states/accounts, hold switches.

        Sampling does not integrate time, auxiliary energy, or dynamics. At a
        phase boundary the saved new-phase value wins (right continuity).
        """
        finite("display time", time_s)
        times = self.columns["time_s"]
        at = float(np.clip(time_s, times[0], times[-1]))
        index = max(int(np.searchsorted(times, at, side="right")) - 1, 0)
        result = {key: values[index] if key in PIECEWISE else float(np.interp(at, times, values))
                  for key, values in self.columns.items()}
        result["time_s"] = at
        return result


def _read_columns(trajectory):
    """Read a rectangular trajectory table and reject missing/nonfinite values."""
    with trajectory.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if REQUIRED - set(fields) or len(fields) != len(set(fields)):
            raise ValueError("Missing or duplicate trajectory columns")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("Trajectory needs at least two samples")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Trajectory rows must match the column count")
    try:
        columns = {key: np.array([row[key] for row in rows], dtype=str if key == "mode" else float) for key in fields}
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid trajectory column values") from error
    if any(not np.isfinite(value).all() for key, value in columns.items() if key != "mode"):
        raise ValueError("Nonfinite trajectory column")
    return columns


def _check_phases(columns, phases):
    """Match phases to saved event indices, preserving arbitrarily close samples."""
    if not phases:
        raise ValueError("Saved run has no phases")
    starts = np.array([phase["start_m"] for phase in phases])
    if not np.isfinite(starts).all() or starts[0] != 0 or np.any(np.diff(starts) <= 0):
        raise ValueError("Saved phase starts must increase from position zero")
    x = columns["position_m"]
    indices = []
    for phase in phases:
        index = int(np.argmin(abs(x - phase["start_m"])))
        if abs(x[index] - phase["start_m"]) > 1e-4 or columns["mode"][index] != phase["command"]["mode"]:
            raise ValueError("Trajectory does not preserve saved phase boundaries")
        indices.append(index)
    if indices[0] != 0 or np.any(np.diff(indices) <= 0):
        raise ValueError("Saved phases must have distinct ordered event samples")
    # A position epsilon can wrongly move a valid pre-event sample into the new
    # phase. Use the actual saved event index, with right continuity at the switch.
    for phase, start, end in zip(phases, indices, [*indices[1:], len(x)]):
        if not np.all(columns["mode"][start:end] == phase["command"]["mode"]):
            raise ValueError("Trajectory modes differ from the saved phase schedule")


def _check_final_totals(columns, summary, route):
    """Require the trajectory and its paired metadata to have identical totals."""
    final = {"time_s": summary["travel_time_s"], "position_m": route.length_m + summary["stop_error_m"],
             "speed_mps": summary["final_speed_mps"], **{key: summary[key] for key in
             ("wheel_traction_work_j", "mechanical_brake_work_j", "resistance_work_j")}}
    if "electrical" in summary:
        final.update({key: value for key, value in summary["electrical"].items()
                      if key.endswith("_j") and key != "maximum_absolute_balance_residual_j"})
    for key, value in final.items():
        if key not in columns or not np.isclose(columns[key][-1], value, rtol=1e-10, atol=1e-6):
            raise ValueError(f"Final trajectory {key} disagrees with run.json")


def load_run(directory):
    """Check pairing, schema, phase boundaries, state bounds and final totals.

    New exports carry a trajectory digest. Older exports are accepted using
    their input-ID, phase schedule and final accounts; they lack byte identity.
    """
    directory = Path(directory)
    record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    trajectory = directory / "trajectory.csv"
    if "trajectory_sha256" in record and hashlib.sha256(trajectory.read_bytes()).hexdigest() != record["trajectory_sha256"]:
        raise ValueError("Trajectory hash does not match run.json")
    inputs = {key: record[key] for key in ("configuration", "code_sha256", "software")}
    if "reference_file_sha256" in record:
        inputs["reference_file_sha256"] = record["reference_file_sha256"]
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    if identity != record["run_id"]:
        raise ValueError("Run ID does not match saved provenance")
    config = record["configuration"]
    route = Route(**{key: tuple(tuple(row) for row in value) for key, value in config["route"].items()})
    columns = _read_columns(trajectory)
    t, x, v = (columns[key] for key in ("time_s", "position_m", "speed_mps"))
    if t[0] != 0 or not np.all(np.diff(t) > 0) or np.any(np.diff(x) < -1e-7):
        raise ValueError("Trajectory time/position must advance from time zero")
    if abs(x[0]) > 1e-6 or abs(x[-1] - route.length_m) > 0.5 or v.min() < -1e-7 or abs(v[-1]) > 0.05:
        raise ValueError("Trajectory violates initial, terminal or forward-motion bounds")
    expected_height = np.array([route.height_m(float(position)) for position in x])
    if not np.allclose(columns["height_m"], expected_height, rtol=0, atol=1e-5):
        raise ValueError("Trajectory height differs from saved route")
    physical_limits = np.array([route.speed_limit_mps(float(position)) for position in x])
    cap = config["control"].get("cruise_speed_cap_mps")
    if np.any(v > physical_limits + 0.05) or (cap is not None and v.max() > cap + 0.05):
        raise ValueError("Trajectory exceeds saved speed constraints")
    if abs(v[0] - config["control"].get("initial_speed_mps", 0)) > 1e-6:
        raise ValueError("Trajectory initial speed differs from configuration")
    _check_phases(columns, record["phases"])
    _check_final_totals(columns, record["summary"], route)
    return SavedRun(record, columns, route)


@dataclass
class PlaybackClock:
    duration_s: float
    speed: float = 1.0
    time_s: float = 0.0
    paused: bool = True

    def __post_init__(self):
        finite("duration_s", self.duration_s, 0)
        self.set_speed(self.speed)

    def set_speed(self, speed):
        finite("playback speed", speed, 0)
        if speed == 0:
            raise ValueError("playback speed must be positive")
        self.speed = speed

    def seek(self, time_s):
        finite("playback time", time_s)
        self.time_s = float(np.clip(time_s, 0, self.duration_s))
        if self.time_s == self.duration_s:
            self.paused = True

    def advance(self, wall_seconds):
        finite("wall seconds", wall_seconds, 0)
        if not self.paused:
            self.seek(self.time_s + wall_seconds * self.speed)
        return self.time_s


def build_view(runs, *, vertical_exaggeration=5.0):
    """Draw a shared simulation clock and illustrative point-train markers."""
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib"))
    import matplotlib.pyplot as plt

    finite("vertical exaggeration", vertical_exaggeration, 0)
    figure = plt.figure(figsize=(12, 9))
    grid = figure.add_gridspec(3, len(runs))
    tracks = [figure.add_subplot(grid[0, i]) for i in range(len(runs))]
    speed = figure.add_subplot(grid[1, :])
    energy = figure.add_subplot(grid[2, :])
    axes = [*tracks, speed, energy]
    figure.subplots_adjust(bottom=0.2, top=0.85, hspace=0.55)
    markers, cursors, texts = [], [], []
    for i, run in enumerate(runs):
        track = tracks[i]
        color = f"C{i}"
        label = f"{i+1}: {run.record['run_id']}"
        points = np.array(run.route.rail_points_m)
        track.plot(points[:, 0], points[:, 1] * vertical_exaggeration, color=color, alpha=0.5)
        track.scatter([0, run.route.length_m], points[[0, -1], 1] * vertical_exaggeration, marker="|", s=160, color=color)
        for position, limit in run.route.speed_limits_mps:
            track.axvline(position, color="gray", linestyle=":", alpha=0.4)
            track.text(position, 0.03, f"{limit:g} m/s", transform=track.get_xaxis_transform(), fontsize=8)
        track.text(0, 1.02, "Station A", transform=track.transAxes, fontsize=8)
        track.text(1, 1.02, "Station B", transform=track.transAxes, ha="right", fontsize=8)
        track.set(xlabel="Along-track position (m)", ylabel=f"Elevation x{vertical_exaggeration:g} (m)")
        marker, = track.plot([], [], marker="s", markersize=12, color=color, label=label)
        markers.append(marker)
        c = run.columns
        speed.plot(c["time_s"], c["speed_mps"], color=color, label=label)
        limits = [run.route.speed_limit_mps(float(x)) for x in c["position_m"]]
        speed.step(c["time_s"], limits, where="post", linestyle=":", color=color, alpha=0.6)
        if "net_supply_energy_j" in c:
            energy.plot(c["time_s"], c["net_supply_energy_j"] / 3.6e6, color=color, label=label)
        texts.append(figure.text(0.1, 0.945 - i * 0.045, "", color=color, fontsize=9))
    cursors = [ax.axvline(0, color="black", alpha=0.4) for ax in (speed, energy)]
    speed.set(xlabel="Simulation time (s)", ylabel="Speed (m/s)", title="Dotted lines: physical speed limits")
    energy.set(xlabel="Simulation time (s)", ylabel="Net energy (kWh)")
    for track in tracks:
        track.legend(fontsize=8, loc="upper right")
    for ax in axes:
        ax.grid(alpha=0.2)
    figure.suptitle("Schematic point-train replay | synthetic / assumed inputs; physical validation pending", y=0.99, fontsize=11)

    def draw(at):
        for i, run in enumerate(runs):
            sample = run.sample(at)
            markers[i].set_data([sample["position_m"]], [sample["height_m"] * vertical_exaggeration])
            net = sample.get("net_supply_energy_j")
            regen = sample.get("regenerative_accepted_power_w")
            electrical_text = ("mechanics only" if net is None else f"net {net/3.6e6:.4f} kWh")
            electrical_text += ("; accepted regen unavailable" if regen is None else f"; accepted regen {regen/1000:.1f} kW")
            texts[i].set_text(f"{run.record['run_id']} | t={sample['time_s']:.2f} s | x={sample['position_m']:.2f} m | "
                              f"v={sample['speed_mps']:.2f} m/s | {sample['mode']} | wheel traction "
                              f"{sample['wheel_traction_power_w']/1000:.1f} kW | {electrical_text}")
        for cursor in cursors:
            cursor.set_xdata([at, at])
        return [*markers, *cursors, *texts]

    draw(0)
    return figure, draw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Directory containing run.json and trajectory.csv")
    parser.add_argument("--pair", type=Path, help="Second saved run on the same simulation clock")
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--snapshot", type=Path, help="Save a static final view without opening a window")
    parser.add_argument("--save", type=Path, help="Optional .gif (Pillow) or .mp4 (ffmpeg) recording")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for path in (args.snapshot, args.save):
        if path and path.exists() and not args.overwrite:
            parser.error("Output file already exists; choose another path or pass --overwrite")
    runs = [load_run(args.run)] + ([load_run(args.pair)] if args.pair else [])
    if len(runs) == 2 and runs[0].record["configuration"]["route"] != runs[1].record["configuration"]["route"]:
        parser.error("Paired runs must use the same route")
    clock = PlaybackClock(max(run.duration_s for run in runs), speed=args.speed)
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib"))
    import matplotlib
    if args.snapshot or args.save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, writers
    from matplotlib.widgets import Button, Slider

    figure, draw = build_view(runs)
    if args.snapshot:
        draw(clock.duration_s)
        figure.savefig(args.snapshot, dpi=150)
    if args.save:
        suffix = args.save.suffix.lower()
        writer = "pillow" if suffix == ".gif" else "ffmpeg" if suffix == ".mp4" else None
        if writer is None or not writers.is_available(writer):
            parser.error("Requested recording writer unavailable; use .gif/Pillow or .mp4/ffmpeg")
        frames = np.linspace(0, clock.duration_s, int(np.ceil(clock.duration_s / clock.speed * 20)) + 1)
        animation = FuncAnimation(figure, draw, frames=frames, interval=50, blit=False, repeat=False)
        animation.save(args.save, writer=writer, fps=20)
    if args.snapshot or args.save:
        plt.close(figure)
        return
    play = Button(figure.add_axes((0.1, 0.04, 0.12, 0.05)), "Play / pause")
    restart = Button(figure.add_axes((0.24, 0.04, 0.1, 0.05)), "Restart")
    scrub = Slider(figure.add_axes((0.1, 0.12, 0.8, 0.025)), "Time (s)", 0, clock.duration_s, valinit=0)
    rate = Slider(figure.add_axes((0.5, 0.05, 0.4, 0.025)), "Speed", 0.25, max(8, clock.speed), valinit=clock.speed)
    last = [time.monotonic()]

    def toggle(_):
        clock.paused = not clock.paused
        last[0] = time.monotonic()

    def seek(value):
        clock.seek(value)
        draw(clock.time_s)
        last[0] = time.monotonic()
        figure.canvas.draw_idle()

    play.on_clicked(toggle)
    restart.on_clicked(lambda _: scrub.set_val(0))
    scrub.on_changed(seek)
    rate.on_changed(clock.set_speed)

    def tick(_):
        now = time.monotonic()
        clock.advance(now - last[0])
        last[0] = now
        scrub.set_val(clock.time_s)
        return draw(clock.time_s)

    animation = FuncAnimation(figure, tick, interval=40, cache_frame_data=False)
    plt.show()


if __name__ == "__main__":
    main()
