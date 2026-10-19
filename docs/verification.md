# Numerical verification

The tests verify implemented equations and software behavior on deterministic
synthetic inputs. They do not calibrate the model to Philippine railway operations.
The pinned environment is Python 3.13.7, NumPy 2.4.1, SciPy 1.17.0 and Matplotlib
3.11.2. The full suite currently contains 67 tests; rerun it after behavior changes.

## Reproduce

```powershell
python -m unittest discover -s tests -v
python scripts/research/preflight.py
python -m railway.run --output results/verification --convergence --sensitivity
```

The first command runs numerical/software tests; preflight independently checks
fixture and source arithmetic without a numerical solver. The scenario command
saves inputs, phase boundaries, source/reference hashes, software versions,
adaptive trajectories, sensitivity cases and convergence results. Use a fresh
directory when outputs already exist. See [experiments](experiments.md) for
coasting and matched-arrival reproduction, and [development](development.md) for
syntax and documentation checks.

## Acceptance criteria

| Quantity or behavior | Criterion |
| --- | --- |
| Inputs | Finite SI values; positive mass; nonnegative forces/power/resistance; conversion efficiencies within declared physical bounds; required evidence and no unresolved active values |
| Analytical verification | Independent fixtures within 0.1% for nonzero reference quantities; individual tests often use tighter tolerances |
| Forward state | Increasing time; nondecreasing position; no material negative speed; zero-speed event roundoff retained |
| Terminal stop | Position error at most 0.5 m and final speed magnitude at most 0.05 m/s |
| Speed constraints | Physical route-limit and optional commanded-ceiling excess at most 0.05 m/s |
| Wheel capability | Traction/brake force within 1 N; traction power within 0.1%; traction and braking mutually exclusive |
| Mechanical balance | Residual at most 0.1% of the maximum traction/brake/resistance work, absolute kinetic/potential change, or 1 kJ |
| Electrical/system balance | Nonnegative dissipative flows within tolerance; recovery/export bounded; full train-boundary energy closes within 0.1% of its energy scale |
| Numerical refinement | Half time/planning steps and tenfold tighter tolerances retain constraints with less than 0.5% normalized change in time/work/electrical totals |
| Matched arrival | Both profiles satisfy the experiment's target/tolerance independently of the timeout; nominal default is $85.0\pm0.1\,\mathrm s$ |
| Search stability | Halving control-grid spacings retains ranking and changes each selected energy by at most the declared 100 kJ band |
| Error classification | Invalid inputs, explicit policy infeasibility, failed audits/arrival/refinement and unexpected numerical failures remain distinct |

Normalized changes use a 1-unit denominator floor for near-zero totals. Refinement
differences are empirical checks, not rigorous bounds on integration error.
Audits cover accepted samples and one-sided phase boundaries; they are not a
continuous-time proof between samples.

## Analytical and motion coverage

[test_dynamics.py](../tests/test_dynamics.py) checks the five versioned
[analytical fixtures](../data/verification/analytical-fixtures.json), additional
limiting cases, input bounds, capability rejections and journey events.

| Case | Independent result |
| --- | --- |
| Constant-force acceleration | 200,000 kg and 200,000 N for 10 s from rest: 10 m/s, 50 m, 10 MJ |
| Constant-force braking | 20 m/s at $1\,\mathrm{m\,s^{-2}}$: 20 s, 200 m and 40 MJ removed |
| Level coast | 10,000 N resistance on 200,000 kg for 10 s from 20 m/s: 19.5 m/s and 197.5 m |
| Lossless downhill coast | Potential-energy decrease becomes kinetic-energy increase with actual mass for gravity and effective mass for inertia |
| Constant wheel power | Above the force/power transition, $v^2=v_0^2+\frac{2Pt}{m_{\mathrm{eff}}}$ |
| Capped level journey | 1000 kg, 1000 N traction/brake, no resistance, nonbinding power, 1000 m and 10 m/s cap: $10\,\mathrm s+\frac{900\,\mathrm m}{10\,\mathrm{m\,s^{-1}}}+10\,\mathrm s=110\,\mathrm s$ |

Other checks cover non-step-aligned stop events, the force/power transition,
zero net force, short trips that never attain a ceiling, initial overspeed,
grade changes, lower local restrictions, downhill coasting intervention, terminal
holding capability and deterministic replay/refinement. Injected unsuccessful,
nonfinite-state and nonfinite-time spatial/time solves must raise `RuntimeError`.
Premature coast stops and insufficient capabilities retain `InfeasibleRun`.

## Energy coverage

[test_electrical.py](../tests/test_electrical.py) checks analytical conversion,
holding auxiliaries, regenerative force/power limits, partial acceptance,
friction substitution, auxiliary reuse, terminal export limits, zero capability
and ideal recovery. It also checks scenario evidence, multi-phase continuity,
electrical refinement, sensitivity contexts and CSV/JSON agreement.

For example, a 10,000 kg train accelerated at $1\,\mathrm{m\,s^{-2}}$ for 10 s requires 500 kJ at
the wheels and 625 kJ with 0.8 motoring efficiency; a 1 kW auxiliary demand adds
10 kJ. The tested interval starts at a nonzero timestamp to distinguish duration
from absolute time.

Independent system closure compares net terminal draw with kinetic/potential
change, resistance, friction, motoring/regenerative losses and auxiliaries.
Potential regenerative generation is never credited as accepted energy.
Algebraically closing electrical bookkeeping alone supplies no independent
physical evidence.

## Experiment and replay coverage

- [Coasting tests](../tests/test_benchmark.py) check independent audits, rejected
  profiles without fabricated metrics, dominance ties/witnesses, all-rejected
  sweeps, refinement, error propagation, figure/table agreement and overwrite guards.
- [Matched-time tests](../tests/test_matched.py) check equivalent constraints,
  impossible requests, audit failures, deterministic serialized replay, numerical
  refinement/arrival failure and fixed-control robustness. A pair found only on
  the refined search grid is provisional because search stability is unverified.
- [Replay tests](../tests/test_replay.py) check provenance/digests, rectangular and
  finite CSV data, phase/mode synchronization, a sample arbitrarily close before
  a switch, endpoint/bounded movement, final energy, capped export round trips,
  playback rates/pause/restart and headless paired rendering with overwrite guards.

The three plot/export/viewer integration tests skip if Matplotlib is absent.
Paired snapshots have been visually inspected and GIF export exercised.
Interactive GUI button operation has not been manually exercised.

## Synthetic baseline

The [scenario](../data/scenarios/synthetic-1km.json) derives 213,790 kg actual mass
from 160,100 kg tare and 826 passengers at 65 kg. Its 16,010 kg rotating allowance,
280 kN traction/brake forces, 1.5 MW wheel power, resistance and route are hypothetical.
The route rises 2.5 m, returns to its original elevation and has a 12 m/s
restriction from 650 m. Coast is requested at 500 m.

| Quantity | Representative result |
| --- | ---: |
| Arrival / peak speed | 81.412529 s / 19.669101 m/s |
| Traction / brake / resistance work | 54.125377 / 45.783361 / 8.342016 MJ |
| Maximum absolute mechanical residual | About 0.007 J |
| Motoring electricity / motoring loss | 63.676914 / 9.551537 MJ |
| Auxiliary energy | 8.141253 MJ |
| Potential regenerative generation | 8.912056 MJ |
| Actual accepted regeneration / export | 0 / 0 MJ |
| Net train-terminal energy | $71.818167\,\mathrm{MJ}\approx19.949491\,\mathrm{kWh}$ |

For this rest-to-rest equal-elevation case,

$$
W_{\mathrm T} = W_{\mathrm B} + W_{\mathrm R}.
$$

With zero accepted regeneration, independent net draw also equals resistance plus
friction work, conversion losses and auxiliaries. Displayed digits demonstrate
reproducibility, not measurement precision. Broader sensitivity, coasting and
matched-arrival results are maintained in [experiments](experiments.md).

## Physical validation limits

Constant service-brake force, immediate commands, constant conversion/auxiliary
inputs and hypothetical resistance remain approximations. Jerk, adhesion dynamics,
load compensation, distributed train geometry, separate tunnel/curve effects,
low-speed regenerative cutoff, storage and an electrical-network solution are
not included. The conservative planner rejects grades without positive net
service-braking deceleration even at zero speed.

Historical specifications, nominal station spacing and annual energy aggregates
do not establish applicable force curves, a full as-built route, or independent
trajectory/energy observations. See [research evidence](research/evidence.md) and
[public-data applicability](research/public-data-review.md). Calibration needs
consistent fleet/route inputs; validation needs independent observations with
compatible loading, controls and energy boundaries. Numerical convergence does
not establish real-world accuracy or achievable operational savings.
