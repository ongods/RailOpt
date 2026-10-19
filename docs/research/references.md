# References

The following bibliography consolidates the sources used or discussed in the project documentation. A citation does not imply endorsement or validation of this model. Page numbers below refer to PDF pages unless stated otherwise; access and applicability limits are recorded in the [evidence record](evidence.md) and [source manifest](source-manifest.json).

## Vehicle and infrastructure evidence

- **JICA (2011), Preparatory Study for LRT Line 2 Extension Project:** [English Part 1](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf), pages 122, 143, 159–160, for geometry categories, loading and specifications; [Japanese edition](https://openjicareport.jica.go.jp/pdf/1000023375.pdf), pages 178–179, for performance loading and motor-rating qualifications; [English Part 2](https://openjicareport.jica.go.jp/pdf/1000023377_02.pdf), pages 196 and 201–207, for proposed extension drawings. [Official catalogue](https://openjicareport.jica.go.jp/740/740/740_118_1000023377.html). The editions describe the same study, not independent measurements; proposed drawings are not as-built evidence.
- **Toshiba (2003), engineering highlights:** [Manila LRT propulsion note](https://www.global.toshiba/content/dam/toshiba/migration/corp/techReviewAssets/tech/review/2003/high2003/high2003pdf/0305.pdf), page 3 / printed page 19. Formation and supplier corroboration, not a complete force/power envelope.
- **LRTA:** [Distance between stations](https://www.lrta.gov.ph/distance-between-stations/), reviewed 18 October 2026. Nominal station spacing; stopping marks and direction-specific chainages remain unspecified. JICA English Part 1 Table 3.4-6, PDF 142, supplies separate 2010 system energy/train-distance context with an unspecified meter boundary.

## Line-selection and operating context

- **JICA (2013):** [LRT-1 appendix](https://openjicareport.jica.go.jp/pdf/12126629_02.pdf), Table 3-1. Historical specifications separated by vehicle generation.
- **JICA:** [Historical railway comparison](https://openjicareport.jica.go.jp/pdf/12247656_01.pdf#page=88), Table 2.1. Historical context, not current local speed permissions.
- **DOTr MRT-3:** [System description](https://www.dotrmrt3.gov.ph/about-us).
- **DOTr/eFOI:** [MRT-3 Czech and Dalian train-specification request](https://www.foi.gov.ph/requests/specifications-of-the-mrt-3-trains-currently-being-used-and-48-dalian-trains-delivered-from-china/). The success response does not itself expose the emailed specifications.
- **JICA (2026):** [MRT-3 rehabilitation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2025/LoanAgreementSign-MRT3.html) and [LRT-1 energy-conservation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2026/LRMC_TA_EnergyConservation.html). Operating context and research leads, not calibration datasets.

## Modelling and numerical methods

- **Tian et al.:** [DC railway energy evaluation](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-est.2015.0025). Background on separating train dynamics from electrical-network energy.
- **Heineken et al.:** [Railway energy-loss modelling](https://link.springer.com/article/10.1007/s40534-023-00322-4). Background on conversion-loss assumptions.
- **Rochard and Schmid:** [Train-resistance estimation](https://journals.sagepub.com/doi/10.1243/0954409001531306). Applicability limits of resistance models; not LRT-2 calibration.
- **Zou et al.:** [Metro rescue/running-resistance study](https://onlinelibrary.wiley.com/doi/10.1155/2020/8869605). Comparable-vehicle context; no coefficients were adopted as Philippine fleet data.
- **SciPy 1.17.0:** [Official `solve_ivp` documentation](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.integrate.solve_ivp.html). DOP853 integration, events and tolerance semantics.

## Related research and data-access leads

- **LRTA/eFOI (2021):** [Rolling Stock Information for LRT-1 and LRT-2](https://www.foi.gov.ph/requests/rolling-stock-information-for-lrt-1-and-lrt-2/), request **LRTA-113014889249**. Public response reviewed; its attachment was inaccessible and supplied no model inputs.
- **Vergel et al. (2022):** [Estimation of transportation energy demand of the Philippines using a bottom-up approach](https://doi.org/10.1016/j.eastsj.2022.100058). Indexed abstract located; direct full-text retrieval was blocked. [UP-NCTS research listing](https://ncts.upd.edu.ph/research/) corroborates the project; no dynamics parameters were imported.
- **Related 2024 study:** [Estimation of local pollutant and carbon dioxide emissions of road and rail transportation in the Philippines](https://doi.org/10.1016/j.eastsj.2024.100133). Aggregate energy/emissions context, not independent trajectory validation.
- **Malaysia MRT Line 2 preprint:** [Comparable-system research lead](https://www.preprints.org/manuscript/202307.0186). Different railway, with ambiguities in extracted resistance notation; no coefficients were adopted.

Failed tender, FOI-attachment, impact-evaluation and environmental-report retrievals are retained with exact URLs and access outcomes in the [source manifest](source-manifest.json). They were discovery leads, not reviewed technical evidence or sources of numerical inputs.
