# Documentation

RailOpt models one forward-moving point train between two stations. SI units are
used internally. Runnable cases remain synthetic; historical fleet specifications
inform selected inputs without establishing physical validation.

| Document | Purpose |
| --- | --- |
| [Model contract](model-contract.md) | System boundaries, equations, controls, integration and energy accounts |
| [Verification](verification.md) | Analytical cases, acceptance criteria, regression coverage and validation limits |
| [Experiments](experiments.md) | Reproducible sensitivity, coasting and matched-arrival studies |
| [Replay](replay.md) | Saved-run viewer, interpolation, controls and recording |
| [Development](development.md) | Module boundaries, checks, data layout and contribution conventions |
| [Parameter register](parameter-register.csv) | Units, applicability, status and source of consequential inputs |
| [Research evidence](research/evidence.md) | Historical vehicle specifications, geometry qualifications and unresolved inputs |
| [Public-data review](research/public-data-review.md) | Assessment of the supplied compilation and remaining data gaps |
| [References](research/references.md) | Bibliography with access and applicability qualifications |
| [Source manifest](research/source-manifest.json) | Source URLs, timestamps, hashes and access outcomes |
| [Source conflicts](research/source-conflicts.csv) | Contradictions retained for review |

Experiment inputs belong in `data/`; generated trajectories, plots and reports
belong in ignored `results/`. Documentation records methods and qualified
findings rather than phase checklists or implementation progress.
