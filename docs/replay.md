# Saved-run schematic replay

## Start playback

The viewer reads a directory containing the standard `run.json` and
`trajectory.csv`. Generate a matched pair first if needed:

```powershell
python -m railway.matched --output results/matched-time
python -m railway.replay results/matched-time/reference --pair results/matched-time/candidate
```

Omit `--pair` to view one saved scenario run. Paired runs must use the same route.
The view shows schematic track elevation, station endpoints, spatial speed
restrictions, point-train markers and synchronized speed/net-energy plots.
Elevation is multiplied by the labeled factor of five; this is not a real map
or a model of individual car bodies.

Controls provide play/pause, restart, playback speed and a time scrubber. Each run
shows its ID, simulation time, position, speed, mode, wheel traction power,
accepted regenerative power and net train-terminal energy, with units. Mechanics-only
runs have no electrical trace. Older electrical exports lacking instantaneous
recovery power display it as unavailable.

## Snapshots and recording

```powershell
python -m railway.replay results/matched-time/reference --pair results/matched-time/candidate --snapshot results/replay.png
python -m railway.replay results/matched-time/reference --pair results/matched-time/candidate --speed 32 --save results/replay.gif
```

Snapshots save a final view without opening a window. GIF export uses Pillow;
MP4 requires an available ffmpeg writer. Writers are optional for interactive
playback. Existing output files require a new path or explicit `--overwrite`.

## Integrity and interpolation

The loader checks provenance, the trajectory digest when present, rectangular
CSV schema, finite/increasing time, forward motion, endpoints, saved route heights
and speed constraints, phase boundaries/modes and final work/electrical totals.
Phase checks use saved event indices so a nearby pre-switch sample retains its
old mode. Historical exports without a digest can be checked against their
provenance, phases and totals, but lack byte identity.

Position, speed, elevation and cumulative energy interpolate linearly between
saved solver samples. Mode, acceleration, forces and powers are held from the
left sample; the saved new-phase value wins at the exact event. This preserves
switch discontinuities while approximating smooth within-phase force changes at
the saved sampling resolution. The viewer never recomputes forces or integrates
energy.

Playback speed changes wall-clock viewing only. Pause, restart, scrubbing and
finished frames add no simulated travel, dwell or auxiliary energy. Paired runs
share one simulation clock; a finished run freezes at its saved final state while
the other continues.

The tests cover these data/clock invariants and headless rendering. Paired output
has been visually inspected and GIF export exercised. Interactive GUI buttons
have not been manually exercised. Replay integrity is separate from the
[physical validation limits](verification.md#physical-validation-limits).
