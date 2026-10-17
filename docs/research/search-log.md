# Research search and access log

Date: 17 October 2026. Bounded follow-up to the initial line comparison; focus is the selected historical LRT-2 vehicle. This is not an exhaustive literature survey.

| Search/lead | Evidence outcome | Use |
| --- | --- | --- |
| LRT-2 tractive effort; rolling-stock power and efficiency | Located LRTA FOI request LRTA-113014889249 and public response | Attachment lead; no numerical values imported |
| LRT-2 running resistance; Davis equation; Manila train resistance | No applicable local coefficient set established | Leave fleet resistance unresolved |
| Toshiba Manila LRT Line 2 propulsion | Retrieved Toshiba 2003 engineering note; also located supplier history | Formation/supplier corroboration only |
| LRTA maintenance tender PB17-167 | Original PDF returned 404; public archive host failed DNS | Do not claim that its technical contents were reviewed |
| LRTA West Extension tender 7203775.pdf | Original returned 404 | Do not transfer proposed extension rolling-stock requirements into existing-train reference |
| LRTA propulsion tender 8763449.pdf | Original returned 404 despite indexed excerpts | Excerpts insufficient to establish motor count and complete power envelope |
| LRT-2 chainage / longitudinal profile / gradient | JICA gives historical geometry categories, maxima and extension planning context | Insufficient to reconstruct one existing interstation rail-height profile |
| Gilmore / Betty Go-Belmonte station distances | Third-party approximate distances surfaced without track stopping-mark definitions | Not accepted as route chainage |
| Anonas–Katipunan / Recto corridor | JICA geometry discussion identifies difficult grade/curve contexts | Route screening, not full profiles |
| Comparable metro resistance literature | Reviewed Rochard/Schmid abstract; Zou et al. running-resistance section; Malaysia MRT Line 2 preprint | Methodology and applicability checks; no local calibration |
| Japanese edition of JICA extension study | Retrieved 514-page PDF; visually reviewed pages 178–179 | AW3 performance condition; service/emergency distinction; one-hour motor rating; brake architecture |
| English JICA Part 2 drawing appendix | Retrieved 246-page PDF; visually reviewed index 196 and plan/profile pages 201–207 | Proposed East Extension geometry only; E-5 PVI annotation conflict retained |
| Government 2020 impact evaluation | Download failed TLS certificate verification | No technical values imported; certificate verification retained |
| DENR revised West Extension EIS | Download returned HTTP 403 | Unreviewed primary-source lead |
| Vergel et al. 2022 energy-demand paper | Indexed abstract located; direct publisher access returned HTTP 403 | Railway operations survey lead; no numerical dynamics inputs imported |
| Related 2024 road/rail emissions paper | Publisher search content describes train-hour/power estimation and scope | Aggregate context only; not independent trajectory validation |

Public LRTA FOI page: https://www.foi.gov.ph/requests/rolling-stock-information-for-lrt-1-and-lrt-2/

Attachment URL disclosed by that page: https://www.foi.gov.ph/documents/51680/img-125091420.pdf

Primary bibliography and machine-readable access results are linked from [the evidence record](evidence.md) and [manifest](source-manifest.json). Search snippets were discovery leads; only retrieved primary content supports factual parameter entries. No requests were submitted and no external messages were sent.

## Reproduction

From the repository root:

```powershell
python scripts/research/preflight.py
```

This offline arithmetic step requires only the Python standard library. Optional screening CSVs are generated with `python scripts/research/preflight.py --output results/preflight`; generated reports are not kept under documentation. It is distinct from the numerical solver tests in [verification.md](../verification.md). To repeat source acquisition, use `python scripts/research/collect_sources.py` with `requests` installed and network access. Cached files are checked by signature and SHA-256; a fresh acquisition can return a different version and must be reviewed against the reference hash.

To check only the newly identified study editions while preserving the other manifest records:

```powershell
python scripts/research/collect_sources.py --only jica-lrt2-japanese-report jica-2011-lrt2-part2
```

To repeat local PDF inspection, install `pypdfium2==5.14.0` into `.research-tools` or the active Python environment and run `python scripts/research/render_sources.py`. The rendering utility extracts text and renders selected pages into `.cache/research/`. PDF rendering required elevated tool execution in this session because the sandbox could not read the installed renderer files; the ordinary offline preflight requires no such access.

The final manifest records the latest access attempt and its timestamp, not the document's publication date. Four downloaded PDFs remain in the local cache; unavailable sources are preserved as leads rather than removed from the audit trail. The [evidence record](evidence.md) records which pages were visually reviewed, translations, design-versus-built limits and unresolved annotations.
