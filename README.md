# RailOpt

Physics-based simulation of one train between two stations, with mechanical work,
optional train-terminal electrical accounting, bounded speed-profile search and
saved-run replay.

The current cases use historical Philippine LRT-2 mass conventions with explicitly
hypothetical route, resistance, capability and electrical inputs. Numerical checks
do not establish real-world accuracy or operational savings. The model has not
been validated against independent operating measurements or by an industry
expert, and must not be used as a single source of truth for engineering or
operational decisions.

## Quick start

From the repository root, using Python 3.13.7 and the pinned dependencies:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m railway.run --output results/synthetic-1km --convergence
```

The scenario runner writes `run.json` and `trajectory.csv` with SI quantities,
configuration, provenance, phase boundaries and energy accounts. Add `--sensitivity`
for the declared parameter study. Generated artifacts stay in ignored `results/`;
use a fresh directory or explicit `--overwrite` when named outputs already exist.

## Experiments and replay

```powershell
python -m railway.benchmark --output results/coasting
python -m railway.matched --output results/matched-time
python -m railway.replay results/matched-time/reference --pair results/matched-time/candidate
```

The coasting benchmark samples an energy-time tradeoff. The matched-time runner
compares cruise-and-brake and coasting controls under the same synthetic
$85.0\pm0.1\,\mathrm s$ arrival requirement, with independent audits and refinement.
It reports the best feasible tested controls, without a global-optimum claim.

A representative matched pair uses 16.5492 kWh at 85.0474 s for the no-coast
reference and 13.7206 kWh at 85.0710 s for the coasting candidate. These are
assumption-dependent simulations. Methods, grids, sensitivity, numerical limits
and provenance are in [experiments](docs/experiments.md).

Replay provides play/pause, restart, rate and time scrubbing. Add
`--snapshot results/replay.png` for a headless final view, or
`--speed 32 --save results/replay.gif` for a short recording. Its schematic
point-train markers read saved data without rerunning physics. See
[replay documentation](docs/replay.md) for integrity checks and writer requirements.

## Model and data

Motion uses

$$
\begin{aligned}
\frac{dx}{dt} &= v, \\
m_{\mathrm{eff}}\frac{dv}{dt} &= F_{\mathrm T} - F_{\mathrm B} - R(v) - mg\frac{dh}{dx},
\end{aligned}
$$

where $m_{\mathrm{eff}}$ is effective inertial mass, $m$ is actual mass,
$F_{\mathrm T}$ and $F_{\mathrm B}$ are wheel traction and brake forces, $R(v)$ is
running resistance and $h(x)$ is rail elevation.
Mechanical traction/brake work, conversion losses, auxiliaries, potential
regeneration and accepted recovery remain separate. Net electrical energy is
train-terminal import minus export; an electrical-network solution is not included.

Internally the simulator uses m, s, kg, N, W and J;
$1\,\mathrm{kWh}=3.6\times10^6\,\mathrm J$.
The optional `cruise_speed_cap_mps` command stays separate from physical route
limits. Scenarios without an electrical section retain mechanics-only behavior.
All consequential inputs declare their evidence and applicability.

| Resource | Purpose |
| --- | --- |
| [Documentation index](docs/README.md) | Model, verification, experiments, replay and development guides |
| [Model contract](docs/model-contract.md) | Equations, assumptions, numerical methods and system boundaries |
| [Verification](docs/verification.md) | Analytical cases, acceptance criteria and validation limits |
| [Development](docs/development.md) | Module responsibilities and repository checks |
| [Synthetic scenario](data/scenarios/synthetic-1km.json) | Runnable inputs with units and evidence |
| [Parameter register](docs/parameter-register.csv) | Sources and qualifications for consequential values |
| [Research evidence](docs/research/evidence.md) | Historical fleet/geometry qualifications and unresolved data |
| [Public-data review](docs/research/public-data-review.md) | Applicability of the supplied public-source compilation |
| [References](docs/research/references.md) | Bibliography and source-access limits |

Original reference data and the byte-preserved public compilation remain in
`data/reference/`. Public nominal spacing and annual energy aggregates do not
supply a complete operational route or validate train-terminal predictions.
