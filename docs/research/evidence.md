# Evidence: historical LRT-2 performance and route geometry

Reviewed 17 October 2026. This consolidates the data review and follow-up evidence dossier. The selected vehicle remains the original four-car LRT-2 train documented in 2011. No present-day fleet calibration is claimed. Current implementation and verification results are in [verification.md](../verification.md).

## Evidence obtained

Two additional primary PDFs were downloaded, hashed, text-extracted and selected pages visually inspected. This brings the local cache to four PDFs, representing the English study in two parts, its Japanese edition, and a separate Toshiba note. The study editions are not independent observations. Exact URLs, byte counts, SHA-256 hashes and access outcomes are in the [manifest](source-manifest.json).

The earlier checks covered the [English JICA Part 1](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf), PDF pages 122, 143, 159 and 160, for historical geometry categories, loading and specifications. The [Toshiba 2003 engineering note](https://www.global.toshiba/content/dam/toshiba/migration/corp/techReviewAssets/tech/review/2003/high2003/high2003pdf/0305.pdf), PDF page 3 / printed 19, independently corroborates the four-motored-car formation and supplier. It contains no usable whole-train wheel-force/power limit.

| Source | Visually inspected pages in this follow-up | Purpose and status |
| --- | --- | --- |
| [JICA Japanese report](https://openjicareport.jica.go.jp/pdf/1000023375.pdf) | PDF 178–179; printed 3-46 and 3-47 | Verified transcription of historical vehicle specifications; useful qualifications absent from the English summary |
| [JICA English Part 2](https://openjicareport.jica.go.jp/pdf/1000023377_02.pdf) | PDF 196 and 201–207; drawing index G-1 and plan/profile E-3 through E-9 | Verified contents of proposed extension drawings; applicability to an actual operating alignment is unverified |

The [JICA catalogue](https://openjicareport.jica.go.jp/740/740/740_118_1000023377.html) links both English PDF parts under the same study. The drawing title blocks identify a preparatory extension study. A government-hosted drawing is evidence of that published design, not proof that the design was built unchanged.

## Performance qualifications recovered

The following are verified published specifications, not measurements. English interpretations below are working translations checked against the visible Japanese labels.

| Parameter | Recovered evidence | Consequence for the model |
| --- | --- | --- |
| Acceleration | Table 3.6-2, PDF 179: 4.68 km/h/s with standing density 7.0 persons/m² | 1.30 m/s² is tied to the AW3 loading convention. Its applicable speed range and test method remain unspecified. |
| Service deceleration | Same table: the label 常用 identifies service braking, 4.68 km/h/s at the same standing density | Record 1.30 m/s² as a service-braking anchor, without assuming constant force or constant net deceleration at every speed. |
| Emergency deceleration | The label 非常 identifies emergency braking, 5.40 km/h/s at the same standing density | Record 1.50 m/s² separately; do not use it to improve the service-braking baseline. |
| Performance loading | Tables 3.6-1 and 3.6-2, PDF 178–179: AW3 has 1,628 total passengers under a 65 kg/person convention | Derived mass is $160\,100+1\,628\times65=265\,920\,\mathrm{kg}$. This is a loading convention, not observed passenger occupancy. |
| Motor output duty | Table 3.6-2, PDF 179: the motor block's one-hour rating label, 1時間定格, precedes voltage; repeated ditto marks apply to output 120 kW, current 80 A and speed 1,915 rpm | 120 kW is a one-hour per-motor output rating. It does not establish a continuous whole-train wheel-power limit. |
| Brake architecture | Section 3.6.1.2, PDF 178: coordinated pneumatic tread braking and regenerative braking | The existence of regeneration does not establish its force curve, low-speed cutoff, conversion efficiency or accepted export. |
| Traction architecture | Same section: all four cars are motored; all bogies are powered; one inverter controls four main motors | This is consistent architecture evidence, but the reviewed passage does not explicitly enumerate all installed motors or inverter groups. Motor count remains unresolved. |

The English table calls its deceleration entry an average; the Japanese table provides the service/emergency distinction and loading qualification. Neither wording defines a complete speed-dependent braking law. The Japanese edition also repeats the AW2 inconsistency already recorded in the [conflict register](source-conflicts.csv); it does not repair it.

The [vehicle reference](../../data/reference/lrt2-2011.json) is now revision v2, and the [parameter register](../parameter-register.csv) records the clarified loading, rating duty, emergency entry and brake architecture. Its status vocabulary remains unchanged: published specification means verified source transcription; derived means arithmetic conditional on those inputs; assumed means hypothetical scenario choice; unresolved means no defensible value has been assigned.

### What the acceleration anchor can constrain

For the AW3 convention, ignoring rotating inertia, the inertial force term is

$$
ma=(265\,920\,\mathrm{kg})(1.30\,\mathrm{m\,s^{-2}})
=345\,696\,\mathrm N.
$$

This is a derived inertial demand, not a measured wheel force. With an explicitly hypothetical rotating allowance of 10% of tare, $m_{\mathrm{eff}}$ becomes $281\,930\,\mathrm{kg}$ and that term becomes $366\,509\,\mathrm N$. To infer traction at an actual test point, add resistance and signed grade force and establish that point's speed and control conditions. On an unspecified grade, neither number alone is a general lower bound on wheel traction.

The existing 826-passenger analytical screening remains useful as a hypothetical calculation. It must not be described as reproducing the published AW3 performance condition. No installed wheel-power value, traction envelope or brake envelope has been filled in from this calculation.

## Geometry recovered, with limits

Part 2 PDF 196 indexes eastern plan/profile sheets E-3 to E-9. PDF 201–207 were visually inspected, rather than relying on text search: these drawings are scanned and their searchable text is largely absent.

| Drawing and PDF page | Legible published design information | Allowed interpretation |
| --- | --- | --- |
| E-3, 201 | Existing/proposed viaduct boundary at chainage 23+181; a +1.0% grade annotation; curve radius 350 m | A proposed alignment connection, not the existing full-line profile |
| E-4, 202 | PVI 23+420 at elevation 20.69 m; PVI 24+029 at 20.69 m; intervening 0.0% grade | Design geometry only; ground-level annotations are separately identified and must not replace rail elevations |
| E-5, 203 | Emerald station reference chainage 24+325; platform boundaries 24+275 and 24+375; rail level 22.38 m on the level portion | Station design reference and platform extent, not an operational stopping mark |
| E-6, 204 | PVI 25+068 at 22.38 m; PVI 25+236 at 20.69 m; intervening −1.0% grade annotation | Rounded design slope; vertical transition details need confirmation before building a route input |
| E-7, 205 | Level rail portion at 20.69 m | Design geometry only |
| E-8, 206 | PVI 26+290 at 20.69 m; PVI 26+667 at 32.00 m; +3.0% grade; Masinag station reference 26+847 | A documented proposed climb; not an as-built measurement |
| E-9, 207 | Level portion at 32.00 m; 180 m curve-radius annotation; proposed viaduct end 27+313 | Proposed terminal/tail geometry, not a current speed permission |

For example, the E-8 rise is $(32.00-20.69)\,\mathrm m=11.31\,\mathrm m$ over a chainage difference of 377 m, consistent with the annotated 3.0% slope. The two station reference chainages differ by 2,522 m. These are derived checks of the design drawing; the latter is not an established stop-to-stop operating distance. Chainage convention, track selection, stopping offsets and final construction revisions would all matter for a real route file.

**Unresolved drawing annotation:** E-5 labels a PVI as 25+197 at elevation 22.38 m, although that sheet covers 24+100–24+800 and places the symbol near 24+200. Preserve the literal annotation and flag the conflict; do not silently replace it with 24+197. This prevents unqualified automatic conversion of the sheets into a continuous profile. Vertical-curve treatment also remains to be established.

No geometry from these proposed extension sheets has been assigned to Gilmore–Betty Go-Belmonte. `actual_route_profile` remains null. A historical extension-design scenario is now a credible candidate for later work if explicitly labelled and its drawing conflicts are resolved; synthetic routes remain the first numerical-verification target.

Other route candidates remain unresolved. Gilmore–Betty Go-Belmonte has no established stopping-mark chainage or full rail profile in this evidence set. Anonas–Katipunan has a historical 5% maximum and an elevated/underground transition, making its missing grade profile material. The Recto–Legarda/Pureza corridor adds tight-curve complications. Historical JICA categories (80 km/h tangent, 60 at 250 m radius, 45 at 175 m radius, 30 on station approach) lack complete spatial boundaries and do not establish current permissions.

Comparable resistance sources remain methodological leads: [Rochard and Schmid](https://journals.sagepub.com/doi/10.1243/0954409001531306) discuss applicability limits; [Zou et al.](https://onlinelibrary.wiley.com/doi/10.1155/2020/8869605) report another metro's resistance in a rescue study. Neither establishes LRT-2 coefficients. The [Malaysia MRT Line 2 preprint](https://www.preprints.org/manuscript/202307.0186) concerns another railway and has unit/exponent ambiguities in extracted text; no coefficients were imported.

## Other leads and access limits

- The government-hosted 2020 LRT-2 impact-evaluation PDF could not be retrieved because TLS certificate verification failed in this environment. Certificate verification was retained. No technical inputs were taken from it.
- The DENR-hosted revised West Extension environmental-impact PDF returned HTTP 403. Its indexed presence is a discovery lead; its technical contents were not verified.
- The LRTA FOI attachment and old tender links remain unavailable as recorded in the manifest. A public successful FOI response does not make its inaccessible attachment reviewed evidence.
- [Vergel et al. (2022), transportation energy-demand study](https://doi.org/10.1016/j.eastsj.2022.100058), is a relevant research lead: its indexed abstract mentions railway operations survey data. Direct publisher retrieval returned HTTP 403, so no force, resistance or efficiency numbers were imported. The authors' [UP-NCTS project listing](https://ncts.upd.edu.ph/research/) corroborates the research project. The relationship between a particular public FOI request and that paper is an inference, not an established provenance chain.
- A [related 2024 emissions study](https://doi.org/10.1016/j.eastsj.2024.100133) uses train-hours and power input to estimate rail energy before emissions, and excludes stations and depots from its electric-rail estimate. Such aggregate estimates are useful context but cannot establish an interstation force curve or independently validate a trajectory.

These searches did not establish a fleet-specific Davis coefficient set, a complete wheel-traction or service-brake curve, an as-built profile for the candidate section, or an independent trajectory with loading and control context. That is the bounded result of this audit, not a claim that such records do not exist.

## Evidence gate and next acquisition step

The evidence now supports more precise historical labels and a proposed-design geometry lead. It still supports only synthetic numerical verification for the first simulator milestone, not calibrated real-route energy estimates.

The smallest useful next acquisition is one consistent dataset for the original train: wheel traction versus speed with load/voltage/duty conditions; service-brake and regenerative capability versus speed; coasting or resistance data; and one direction's as-built rail chainage, elevation and restrictions. A matched, independent trajectory is needed for later physical validation. [The data-request draft](data-request-draft.md) specifies these fields and acceptable alternatives. It has not been sent.

Reproduce downloads and page rendering using the [search log](search-log.md). The source cache and rendered images are local, ignored research files. Hashes identify the reviewed PDFs; hashes alone do not prove a parameter's applicability.

The original research audit checked the signatures, byte counts and SHA-256 hashes of all four cached PDFs, the 37-row parameter register, and the mass/conversion/drawing arithmetic above. Current numerical verification is maintained separately in [verification.md](../verification.md). Neither transcription checks nor numerical convergence establish physical validation.
