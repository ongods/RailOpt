# Development and repository conventions

## Environment and checks

Run commands from the repository root. The pinned environment is Python 3.13.7
with NumPy 2.4.1, SciPy 1.17.0 and Matplotlib 3.11.2.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q railway scripts tests
python scripts/research/preflight.py
python scripts/check_docs.py
```

The repository uses standard-library `unittest`; no separate linter or type-check
configuration is established. The documentation check resolves local Markdown
links and anchors without accessing external websites. Preflight checks fixture
arithmetic and historical parameter calculations; it does not run the train ODE.

Matplotlib imports are deferred until plotting/viewing. The plot/viewer integration
tests skip when it is unavailable. An interactive Matplotlib backend is needed
for local playback; headless snapshots use Agg. MP4 encoding is optional.

## Code boundaries

| Module | Responsibility |
| --- | --- |
| `railway/physics.py` | Validated vehicle/command data, resistance and force balance |
| `railway/integration.py` | Time-domain motion/work integration, events and shared refinement settings |
| `railway/electrical.py` | Regenerative power bounds and cumulative train-terminal energy accounts |
| `railway/journey.py` | Route data, backward braking envelope, forward planning and time replay |
| `railway/audit.py` | Independent sample/phase constraint and energy audits for electrical experiments |
| `railway/run.py` | Scenario loading, summaries, sensitivity, provenance and standard trajectory export |
| `railway/benchmark.py` | Coasting sweep, sampled frontier, report and CLI |
| `railway/matched.py` | Matched-arrival search, independent replay/refinement and fixed-control robustness |
| `railway/plotting.py` | Static comparison figures |
| `railway/replay.py` | Saved-output validation/interpolation and schematic playback |

The existing `railway.benchmark.audit_profile` import remains available for
compatibility; the implementation lives in `railway.audit`. Replay never invokes
the solver. A single `refined_settings` helper keeps time/planning convergence
choices consistent across scenario, benchmark and matched-time runners.

## Inputs and outputs

- `data/scenarios/` holds runnable SI configurations with evidence for every
  active parameter group. A scenario declares its scope and assumptions.
- `data/experiments/` holds search grids, arrival requirements and comparison
  tolerances independently of vehicle/route inputs.
- `data/verification/` holds analytical fixtures independent of numerical solvers.
- `data/reference/` holds historical source transcriptions and the original
  public-data compilation. Reference files are not runnable configurations.
- `docs/` holds enduring model, verification, experiment and research documentation.
- `results/` holds generated artifacts. Use a fresh output directory for a new
  experiment; explicit `--overwrite` replaces the command's named outputs.
- `.cache/` and `.research-tools/` hold local research/rendering resources.

Run IDs hash configuration, module contents and software versions. Historical
reference and trajectory hashes are stored when applicable. A harmless source
refactor changes IDs even when numerical results remain identical. Preserve old
results with their original configuration and source hashes.

## Making changes

Trace changes through loading, forces, planning, integration, accounting, exports
and tests. Keep existing public interfaces unless a change has a clear reason.
Use explicit SI names, small functions and the existing dataclasses. Add physics
or boundary regression tests for behavior changes; use analytical reductions and
independent energy identities instead of tests that repeat implementation logic.

Use `ValueError` for invalid inputs, `InfeasibleRun` for explicit capability or
policy rejections, and `RuntimeError` for integration or accounting failures.
Unexpected numerical/software failures must propagate rather than appearing as
rejected driving policies. A physically completed run can separately fail arrival,
audit or refinement checks.

No new physics, railway constants or dependency is justified solely by cleanup.
Record consequential parameter evidence in the existing data/register structures.
Distinguish model assumptions, numerical error and software defects when changing
scientific behavior. See [verification](verification.md) for acceptance criteria.

## Research utilities

`scripts/research/collect_sources.py` requires `requests` and network access. It
downloads explicitly listed PDFs and updates the source manifest, so run it only
when intentionally refreshing evidence. A new download may differ from the
reviewed hash and needs another applicability review.

```powershell
python scripts/research/collect_sources.py --only jica-lrt2-japanese-report jica-2011-lrt2-part2
python scripts/research/render_sources.py
```

Rendering requires `pypdfium2==5.14.0` in the environment or `.research-tools`.
The utility extracts text and selected page images into `.cache/research/`.
Rendering and matching hashes do not themselves verify scientific applicability;
reviewed pages, translations and limitations belong in the evidence record.
