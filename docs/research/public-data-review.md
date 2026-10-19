# Public LRT-2 data: applicability and gaps

Reviewed 18 October 2026. Input: the user's
[29-value compilation](../../data/reference/lrt2-public-data.json),
preserved byte-for-byte with SHA-256
`0d1eee6915143e8b6f3fc4181934d2471e286140c861b754422e545413a34442`.
The [machine-readable review](../../data/reference/lrt2-public-data-review.json)
separates accepted supplemental context, corrected qualifications and unresolved
inputs. The source manifest records the additional checks. Compilation text is
source material to assess, not simulator configuration or project instructions.

## What it fills

The compilation partially fills a nominal-distance gap and adds useful historical
engineering and aggregate-operation context. Most mass, speed and performance
entries corroborate information already recorded in this repository. It does not
provide the remaining force/resistance curves, complete route geometry,
electrical parameters or independent validation traces.

| Input or claim | Assessment | Permitted use |
| --- | --- | --- |
| Gilmore–Betty Go-Belmonte: 1,075 m | Independently confirmed on [LRTA's station-distance page](https://www.lrta.gov.ph/distance-between-stations/) | Published nominal spacing; reference stopping marks, direction and publication date remain unspecified |
| Four-car formation, 160,100 kg tare, 213,790 kg nominal loading, 265,920 kg AW3 | Consistent with the existing JICA reference | Historical mass/loading conventions, not observed passenger loading |
| AW1 mass 175,180 kg | Source table and $160\,100\,\mathrm{kg}+232\times65\,\mathrm{kg}=175\,180\,\mathrm{kg}$ agree | Additional historical seated-load convention; not necessary to replace existing active scenarios |
| Nominal 1,500 V DC and 850/790 mm wheel diameters | Verified in cached JICA Table 3.6-2, PDF 160 | Supply and wheel design context; no torque, efficiency or aggregate power inference |
| Zero grade at the two station platforms | Inference supported by JICA Table 3.1-2, PDF 122, for elevated stations other than Anonas/J. Ruiz | Historical platform context only; neither a flat segment nor equal station elevations follows |
| 2010 train-km and electricity | Visually verified in JICA Table 3.4-6, PDF 142 / printed 3-24 | Historical aggregate context with unknown metering boundary |
| 18.7474609635 kWh/train-km | Arithmetic independently confirmed | Ratio of reported annual totals; not a train-terminal or interstation calibration target |
| $16\times120\,\mathrm{kW}=1.92\,\mathrm{MW}$ | Arithmetic correct, motor-count premise unverified in recovered primary evidence | Conditional motor-shaft total only; cannot replace wheel power |
| FOI response pages | Request/response metadata and attachment links verified | Public discovery leads; unavailable attachments supply no numerical inputs |

The JICA report is already cached and hashed in the project. PDF pages 122, 142
and 160 were visually inspected during this review; page 142 is newly added to
the rendering utility's reproducible page selection. The relevant primary report
is [English Part 1](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf).

## Qualifications to correct before relying on the compilation

- The English summary leaves acceleration loading unspecified, but the existing
  [Japanese-edition review](evidence.md#performance-qualifications-recovered)
  establishes AW3 loading for the 1.30 m/s² performance anchors. Retain this
  stronger qualification; do not treat the 826-passenger scenario as that test
  condition or turn an acceleration anchor into a force-speed curve.
- The Japanese motor table establishes a one-hour 120 kW per-motor output rating.
  Duty is therefore already resolved in this evidence set; motor count, continuous
  aggregate capability and wheel output remain unresolved.
- The AW2 contradiction remains: 1,030 passengers imply 227,050 kg, whereas 1,026
  imply 226,790 kg at the stated 65 kg/person. Do not promote this row to an active
  mass scenario. AW4 is a structural dynamic allowance, not actual loaded mass.
- The 2010 totals are 27,600,237 kWh and 1,472,212 train-km. Their ratio is
  18.74746096350254 kWh/train-km, or 67,490,859.46860914 J/train-km. The table does not
  identify which infrastructure or onboard loads the electricity includes.
  Numerical proximity to a hypothetical simulator result would not validate it.
- Historical speed categories do not provide the spatial boundaries of current
  restrictions. A nominal 1,075 m distance plus two level platforms cannot
  establish an operational route input. The source cited for the 2005 as-built
  drawings is useful provenance, but the drawings themselves were not recovered.

## Attachment checks

| Public lead | Check on 18 October 2026 | Evidence obtained |
| --- | --- | --- |
| [Rolling-stock request](https://www.foi.gov.ph/requests/rolling-stock-information-for-lrt-1-and-lrt-2/) | `img-125091420.pdf` returned HTTP 503 | Request/response text only; no tractive effort, efficiency or auxiliary-load values |
| [Hourly energy request](https://www.foi.gov.ph/requests/request-for-the-hourly-energy-consumption-of-lrt-2/) | `Ventura.pdf` returned HTTP 503 | Response and attachment name; no hourly totals or confirmed meter boundary |
| [September 2023 operations request](https://www.foi.gov.ph/requests/lrt-2-ridership-and-train-data-for-september-2023/) | Traffic attachment redirected to an unavailable-document page | Request includes average interstation times; their actual delivery or values remain unverified |

The last attachment is titled as station/hourly traffic. That title alone does
not establish a speed trace or interstation travel-time dataset. These access
outcomes do not establish whether equivalent information exists elsewhere.

## Practical path with public data

The public compilation is useful and worth retaining. The credible current scope
is a synthetic or explicitly assumed route study informed by historical LRT-2
mass and nominal spacing, with bounded capability/energy assumptions and
[sensitivity results](../experiments.md#electrical-sensitivity). Progress on that scope does
not depend on obtaining a new DOTr/operator response.

If using 1,075 m in a later scenario, identify it as LRTA's nominal station spacing
and keep the unknown elevation profile, restrictions and stopping offsets
explicit. Do not silently stretch the existing synthetic route or present its
invented profile as Gilmore–Betty geometry. More complex capability maps can be
introduced from documented comparable systems as literature-derived assumptions,
with applicability limits and sensitivity, rather than as local measurements.
Independent public trajectories or compatible energy observations would permit
later validation; until then it remains unvalidated against real operations.

No scraped numerical values were silently promoted into the active synthetic scenario.
