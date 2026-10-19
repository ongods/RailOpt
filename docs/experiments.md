# Synthetic experiments

These studies use the [synthetic 1 km scenario](../data/scenarios/synthetic-1km.json).
Historical LRT-2 mass conventions inform the example; route, resistance,
capability, conversion and electrical inputs remain hypothetical. Results are
simulated train-terminal quantities, not measured consumption or proven railway
savings. Energy conversions use $1\,\mathrm{kWh}=3.6\times10^6\,\mathrm J$.

## Reproduction and provenance

Run from the repository root with [requirements.txt](../requirements.txt):

```powershell
python -m railway.run --output results/sensitivity --sensitivity --convergence
python -m railway.benchmark --output results/coasting
python -m railway.matched --output results/matched-time
```

Use a new directory when an output already exists, or explicitly pass
`--overwrite`. JSON records retain complete configuration, assumptions, source
hashes, software versions and solver settings. Original generated artifacts stay
in ignored `results/`; they are not required in a fresh checkout. Source changes
alter IDs even when numerical values remain the same.

Representative values below were obtained on 18 October 2026 with Python 3.13.7,
NumPy 2.4.1 and SciPy 1.17.0; figures used Matplotlib 3.11.2. Historical identifiers
are retained as provenance rather than promises of current source hashes:

| Study | Historical ID | Original output directory under `results/` |
| --- | --- | --- |
| Sensitivity baseline | `824be8b788a95a6f` | `electrical-sensitivity-2026-10-18` |
| Coasting benchmark | `dadf508825529cc9` | `coasting-benchmark-2026-10-18` |
| Matched-time comparison | `da6dcfdab0bfe86d` | `matched-time-verified-2026-10-18` |

## Electrical sensitivity

The runner evaluates 36 deterministic cases: 14 built-in mechanical stresses and
22 scenario-declared electrical cases. Electrical cases change one assumption while retaining route,
vehicle and driving controls. Their adaptive sample grids can differ; compare
endpoint quantities within numerical tolerance rather than requiring identical
arrays. Mechanical stresses can change arrival time and are not matched-time
strategy comparisons.

The baseline accepts no regeneration. Capability/efficiency sweeps therefore use
a separate acceptance-one reference to expose their effects; each case records
its comparison reference explicitly. Acceptance is a declared usable fraction
before allocating auxiliary reuse and terminal export, not a network solution.

| Parameter/context | Values tested | Net terminal energy (kWh), in the same order |
| --- | --- | --- |
| Motoring efficiency; baseline acceptance 0 | 0.75 / 0.85 / 0.95 | 22.308 / 19.949 / 18.088 |
| Auxiliary power; baseline acceptance 0 | 50 / 100 / 150 kW | 18.819 / 19.949 / 21.080 |
| Regenerative acceptance | 0 / 0.5 / 1 | 19.949 / 18.712 / 17.474 |
| Regenerative efficiency; receptive reference | 0.50 / 0.75 / 0.90 | 18.299 / 17.474 / 17.233 |
| Regenerative wheel force; receptive reference | 70 / 140 / 210 kN | 17.834 / 17.474 / 17.354 |
| Regenerative wheel power; receptive reference | 375 / 750 / 1125 kW | 18.497 / 17.474 / 17.351 |
| Export ceiling; receptive reference | 0 / 250 / 500 kW | 19.251 / 18.230 / 17.474 |

All 36 cases completed. Electrical-case arrivals match the 81.412529 s baseline
within approximately $7.6\times10^{-10}\,\mathrm s$. Enabling the reference acceptance permits about
2.476 kWh generation under the declared caps. With export disabled, auxiliaries
still reuse about 0.698 kWh: zero export and zero acceptance are different cases.

At zero recovery, the independent energy check is

$$
E_{\mathrm{net}} = \frac{W_{\mathrm T}}{\eta_T} + P_A T,
$$

where $T$ is actual journey duration. Conversion, capability and export bounds can saturate each
other. These selected stress ranges are not confidence intervals; energy spans
across different ranges/reference contexts do not rank parameter importance.
Individual sensitivity cases use runtime checks and are not all separately refined.

## Coasting tradeoff

The [coasting experiment](../data/experiments/coasting-benchmark.json) changes only
the requested coast position. No requested coast and the scenario's 500 m switch
are included. Service braking and speed limits override the request. Every
sample uses the existing planner/time replay and a separate energy/constraint audit.

The 44 declared controls produce 39 feasible profiles and five policy rejections.
Departure at 0 m cannot coast from rest; requests at 1, 5, 10 and 25 m stop early.
These are rejections of this policy, not proof of general route infeasibility.
The 25 m rejection and 50 m success bracket sampled outcomes only.

| Coast request | Arrival (s) | Net energy (kWh) | Brake work (MJ) | Auxiliary energy (kWh) |
| --- | ---: | ---: | ---: | ---: |
| None | 80.7314 | 22.96628 | 55.0122 | 2.24254 |
| 50 m | 172.6965 | 8.32307 | 5.6202 | 4.79712 |
| 75 m | 129.0248 | 8.29722 | 8.7030 | 3.58402 |
| 150 m | 95.4036 | 10.28985 | 16.4898 | 2.65010 |
| 350 m | 82.7785 | 16.04332 | 33.9878 | 2.29940 |
| 500 m | 81.4125 | 19.94949 | 45.7834 | 2.26146 |

The 75 m switch has the lowest sampled energy, but takes about 129 s. It does not
establish a matched-time benefit over the approximately 81 s reference. The slower
50 m case loses its traction advantage through additional auxiliary consumption.
Earlier coasting need not minimize net terminal energy.

Of the feasible samples, 26 lie on the sampled frontier, including numerical ties;
13 have dominance witnesses. Comparison bands are 0.01 s and 100 J. Eight selected
cases retain their status under half time/distance steps and tenfold tighter
tolerances; the maximum normalized change is about $2.18\times10^{-8}$ against a $0.005$ criterion.
Accepted regeneration remains zero; potential generation is never credited.

Outputs are `benchmark.json`, `profiles.csv`, `energy-time.png`, `energy-time.svg`
and `coasting-feasibility.md`. The JSON/report retain rejected-case reasons and
audits; rejected cases have no fabricated time/energy pair. Frontier lines are
visual guides between samples, not interpolated feasible trajectories.

## Matched-arrival comparison

The [matched-time experiment](../data/experiments/matched-time.json) minimizes net
train-terminal energy over commanded cruise ceiling and one coast position.
Both profiles must run rest-to-rest over the same 1000 m, with identical
physical/electrical inputs and $\lvert T-85.0\,\mathrm s\rvert\le0.1\,\mathrm s$, where $T$ is arrival time. This target is
synthetic, not a timetable. The timeout remains separate; no waiting is added.
The reference has no requested coast and uses its lowest-energy feasible tested cap.

A bounded cap/coast grid starts at 2 m/s and 100 m spacing over 12–20 m/s and
100–900 m. A second search halves both spacings. Each observed adjacent cap/time
crossing is bisected nine times with explicit simulation/audit, without global
monotonicity or feasibility inferred from interpolation.

| Quantity | No-coast reference | Coasting candidate |
| --- | ---: | ---: |
| Commanded ceiling (m/s) | 15.031250 | 16.250000 |
| Coast request (m) | None | 300 |
| Arrival (s) | 85.047369 | 85.070984 |
| Arrival minus target (s) | 0.047369 | 0.070984 |
| Net terminal energy (kWh) | 16.549188 | 13.720625 |

Reference minus candidate energy is 2.828564 kWh; the candidate takes 0.023615 s
longer. The coarse search evaluates 122 controls with 46 meeting arrival constraints;
the refined search evaluates 288 with 96 meeting them. Remaining profiles miss
the arrival band. Both grids select the same pair, giving zero selected-energy
change within the declared 100 kJ search-stability band.

Selected controls are serialized and independently replayed, then rerun with
half time/distance steps and tenfold tighter tolerances. Both arrival constraints
and audits pass. The largest nominal relative time/work/electrical change is below
$5\times10^{-8}$ against the $0.005$ criterion. Search refinement and integration refinement
answer separate questions. A pair found only on the refined grid is retained as
provisional; it cannot pass the coarse/fine search-stability gate. A failed search
does not prove global infeasibility.

The result is the best feasible tested pair within these bounds and policy,
without a global-optimum claim. Outputs are `comparison.json`, `comparison.md`,
PNG/SVG comparison figures, and standard `reference/` and `candidate/` saved runs.
An absent or unverified comparison returns a nonzero CLI status and retains
diagnostics. See [replay](replay.md) for viewing the saved pair.

## Fixed-control robustness

Both nominal controls are replayed without retuning across nine joint assumptions.
Every pair passes arrival/audit/refinement checks. Reference minus candidate:

| Auxiliary power (kW) | Acceptance 0 | Acceptance 0.5 | Acceptance 1 |
| ---: | ---: | ---: | ---: |
| 50 | 2.828892 kWh | 2.621256 kWh | 2.421212 kWh |
| 100 | 2.828564 kWh | 2.620928 kWh | 2.413292 kWh |
| 150 | 2.828236 kWh | 2.620600 kWh | 2.412964 kWh |

The candidate remains lower beyond the larger of 100 J and the sum of both
energy-refinement changes. This is an empirical numerical comparison band, not
a rigorous error bound. Greater recovery narrows the difference; auxiliary demand
has little effect on the ranking because durations are close. Neither strategy is
retuned under changed assumptions, and the ranges are not confidence intervals.
Loading, resistance, conversion assumptions and missing operational data still
limit conclusions. Numerical verification remains separate from physical validation.
