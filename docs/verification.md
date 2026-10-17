# Numerical verification

Verified 17 October 2026 with Python 3.13.7, NumPy 2.4.1 and SciPy 1.17.0. This verifies the implemented equations on synthetic inputs. Local fleet calibration and physical validation remain pending.

## Reproduce

From the repository root, with [requirements.txt](../requirements.txt) installed:

```powershell
python -m unittest discover -s tests -v
python scripts/research/preflight.py
python -m railway.run --output results/synthetic-1km --sensitivity --convergence
```

If that output already exists, choose another directory or explicitly add `--overwrite`. Generated files are ignored rather than committed as research evidence. `run.json` retains the full configuration, reference-file hash, source-module hashes, software versions, phase boundaries, baseline metrics and optional convergence results. `trajectory.csv` includes adaptive samples with SI units in column names.

## What passed

**20 unittest tests passed**, including all five versioned analytical fixtures. These exercise the numerical ODE against independent expected results rather than rechecking only fixture arithmetic.

| Check | Coverage and outcome |
| --- | --- |
| Constant-force acceleration | 200,000 kg, 200,000 N, 10 s: 10 m/s, 50 m, 10 MJ; numerical result matches the fixture. |
| Constant-force braking | 20 m/s at 1 m/s²: 20 s, 200 m, 40 MJ removed. A separate non-step-aligned stop is localized without clipping. |
| Level coast | 10,000 N resistance on 200,000 kg: 19.5 m/s and 197.5 m after 10 s from 20 m/s. |
| Lossless downhill coast | A 5 m descent exchanges 9,806,650 J of potential energy with kinetic energy using actual/effective mass consistently. |
| Constant power and transition | The 1 MW fixture above transition reproduces its expected speed/work. A separate departure resolves the transition at 5 m/s before constant-power acceleration. |
| Force balance and controls | Zero net force gives constant speed; downhill cruise can use braking; downhill coast can accelerate; partial commands respect limits; zero wheel power cannot produce launch traction. |
| Route and endpoints | A restricted, graded 1 km journey uses traction/cruise/coast/braking. Short trips remain below top speed; both decreasing and increasing restrictions and nonzero initial speed are covered. |
| Work and capability | Nonnegative cumulative dissipative work, wheel-force/power bounds, exclusive traction/braking, and mechanical energy closure are checked along accepted trajectories. |
| Feasibility | Excessive initial speed, insufficient starting force, insufficient braking/holding force, premature coast stops and timeouts are rejected. A train unable to sustain its initial uphill speed may slow and complete feasibly. |
| Inputs and provenance | Negative/nonfinite physical inputs, invalid commands/routes, missing evidence, unresolved vehicle fields, mismatched mass derivations and unsupported unit declarations are rejected. |
| Refinement and determinism | A graded/restricted journey is rerun with smaller time/distance steps and tighter relative tolerance. Endpoint/constraint targets hold and time/work changes remain below 0.5%. Identical settings reproduce identical arrays in the test environment. |

Runtime journey acceptance also checks terminal errors, local speed excess and mechanical energy residual. Numerical stop roots can have signed floating-point speed roundoff around $10^{-14}\,\mathrm{m\,s^{-1}}$; that raw value is retained. This is distinct from physically allowing reverse motion.

## Synthetic 1 km example

The [scenario](../data/scenarios/synthetic-1km.json) uses the historical 160,100 kg tare and report convention of 826 passengers at 65 kg, giving 213,790 kg actual mass. The 16,010 kg rotating allowance, 280 kN traction/brake forces, 1.5 MW wheel power, Davis coefficients and route are all hypothetical. There is no claim that those limits describe an LRT-2 train. The route rises 2.5 m and returns to its initial elevation, has a 12 m/s restriction from 650 m, and requests coast from 500 m.

| Quantity | Baseline result |
| --- | --- |
| Travel time | 81.412529 s |
| Peak speed | 19.669101 m/s |
| Wheel traction work | 54.125377 MJ |
| Mechanical brake work removed | 45.783361 MJ |
| Resistance work | 8.342016 MJ |
| Absolute terminal position error | About $3.1\times10^{-8}\,\mathrm m$ |
| Terminal speed magnitude | Below $10^{-12}\,\mathrm{m\,s^{-1}}$ |
| Maximum absolute mechanical-energy residual | About 0.008 J |
| Local speed excess | None above numerical tolerance |

For an ideal rest-to-rest run returning to its initial rail elevation,

$$
\Delta K=\Delta U=0
\quad\Longrightarrow\quad
W_{\mathrm T}=W_{\mathrm B}+W_{\mathrm R}.
$$

The synthetic replay satisfies this balance within numerical error. Brake work is not regenerated electrical energy. The many displayed numerical digits establish reproducibility only; they do not represent route or vehicle measurement accuracy.

With `--convergence`, maximum time step changes from 0.25 to 0.125 s, spatial planning step from 5 to 2.5 m, and integration tolerances tighten by a factor of ten. On this example, the largest relative change among travel time and the three nonzero work totals was below $10^{-8}$, well below the $0.005$ acceptance target. Residuals need not decrease monotonically at floating-point/event-location scales; both runs remain comfortably inside the energy criterion.

The `--sensitivity` run completed 14 declared cases: baseline, empty/AW3 passenger conventions, ±20% perturbations to resistance, wheel power, traction force, service-brake force and rotating mass, and a level-route comparison. All were feasible in this run. Travel times ranged approximately 76.50–86.16 s and wheel traction work 43.94–57.90 MJ. These deliberately selected stresses are not probability distributions or confidence bounds. Because travel times differ, the results are not equal-time optimization or demonstrated energy savings. Each case's actual configuration and result are exported.

## Remaining model limits

The service-brake envelope is constant force, and controls act without delay or jerk limits. No verified load-compensation law, adhesion dynamics, separate curve/tunnel resistance, finite train length, electrical conversion, auxiliaries or accepted regeneration is included. The conservative planner rejects grades where maximum service braking cannot provide positive net deceleration at zero speed. It is not a general signalling or stopping-safety tool.

The next useful advance is a defensible capability/resistance dataset and one as-built section with an independent trajectory. Until then, the appropriate claim is **numerically verified synthetic mechanics; physical calibration and validation pending**.

## Repository consolidation

The overlapping data-review and dated evidence-gathering reports were consolidated into [research/evidence.md](research/evidence.md). The generated analytical Markdown report and three screening CSVs were removed from documentation; the arithmetic utility can regenerate the CSVs under `results/preflight`. The source manifest, conflict register, parameter register and unsent data request were retained. The [model contract](model-contract.md) is the equation/method reference; the [Phase 1 plan](phase-1-plan.md) holds scope and acceptance criteria.
