# Phase 1: scope, evidence and acceptance criteria

Initial research: 15 October 2026. Updated: 17 October 2026. A minimal numerical mechanics core is implemented; [verification](verification.md) is separate from physical calibration. Equations and numerical conventions are maintained in the [model contract](model-contract.md), and source findings in the [evidence record](research/evidence.md).

## Scope and target choice

Study one train, one direction and fixed mass per run, including traction, cruise, coast, service braking and mechanical work. The question is whether a transparent model reproduces basic motion and exposes sensitivity to uncertain inputs. Electrical-network modelling, optimization and a user interface remain later work.

Use the original LRT-2 four-car train documented in 2011 as a historical mass/configuration reference. Actual route selection remains open; runnable routes are explicitly synthetic.

| Target | Public technical evidence reviewed | Limitation and decision |
| --- | --- | --- |
| LRT-2 | JICA's 2011 study links configuration, loading, propulsion and performance; its Japanese edition adds loading and motor-duty qualifications. | Historical specifications do not establish current force curves. First choice because important inputs are documented together. |
| LRT-1 | JICA's 2013 Volume 1 appendix, Table 3-1, separates three historical vehicle generations. | A single generation/year must be selected. Close second; do not mix generations. |
| MRT-3 | DOTr system description, JICA rehabilitation reporting and historical comparison tables provide context. | Choose a specific Czech or Dalian vehicle and consist. An FOI success page whose specifications were emailed is not an accessible parameter dataset. More verification is needed in this evidence set. |

Primary references: [LRT-2 study](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf), [LRT-1 appendix](https://openjicareport.jica.go.jp/pdf/12126629_02.pdf), [DOTr MRT-3 description](https://www.dotrmrt3.gov.ph/about-us), [JICA historical comparison, Table 2.1](https://openjicareport.jica.go.jp/pdf/12247656_01.pdf#page=88), and [MRT-3 FOI response](https://www.foi.gov.ph/requests/specifications-of-the-mrt-3-trains-currently-being-used-and-48-dalian-trains-delivered-from-china/).

The [2026 MRT-3 rehabilitation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2025/LoanAgreementSign-MRT3.html) reports 60 km/h after rehabilitation; the historical comparison lists 65 km/h. Neither can be silently substituted for a dated local speed permission. The [2026 LRT-1 energy-conservation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2026/LRMC_TA_EnergyConservation.html) is a research lead, not a calibration dataset.

## Evidence and minimum physical inputs

The [parameter register](parameter-register.csv) records applicability, units, sources and qualifications. Published specifications are verified transcriptions rather than measurements; derived values are conditional arithmetic; assumed values are scenario choices; unresolved values remain unassigned. Runnable configurations label hypothetical values explicitly and retain their basis.

| Required input | Purpose | Evidence status |
| --- | --- | --- |
| Composition, empty mass, passenger mass and count | Actual train mass and gravity | Original four-car tare is 160,100 kg. The report uses 65 kg/person. Occupancy is a scenario convention without observations. |
| Equivalent rotating mass | Effective inertia and kinetic energy | Unresolved for LRT-2; separately assumed in scenarios, without scaling with passenger mass. |
| Wheel traction versus speed | Attainable acceleration and power | Full curve unresolved. Scenarios declare finite low-speed force and wheel-power limits. |
| Service-brake envelope | Deceleration, stopping and holding | Nominal service anchor known; force curve, blending and delays unresolved. Constant force is an explicit first approximation. |
| Whole-train running resistance | Coasting and losses | Local Davis coefficients unresolved. Keep whole-train SI coefficients separate from per-tonne/km/h formulations. |
| Track distance, rail height, stops and speed restrictions | Geometry, gravity and constraints | No complete as-built candidate profile established. Ground elevation and station-centroid spacing are insufficient. |
| Initial conditions and controls | Reproducible experiment | Declared scenario inputs; service braking takes priority over the coast request. |
| Extra curve/tunnel effects and adhesion, if modelled | Refine applicability | Not separately implemented. Non-slipping wheel-force limits and no additional curve/tunnel forces are explicit assumptions. |
| Efficiency, auxiliaries, regenerative capability and acceptance | Electrical boundary only | Unresolved and outside the implemented mechanical core. |
| Independent trajectories and metered energy | Physical validation | Not available in this evidence set. Specifications and annual totals are insufficient. |

[Japanese JICA Table 3.6-2, PDF 179](https://openjicareport.jica.go.jp/pdf/1000023375.pdf#page=179) specifies 1.30 m/s² acceleration and service deceleration at 7.0 standing passengers/m², corresponding to AW3: 1,628 passengers and a derived 265,920 kg. Emergency deceleration is separately 1.50 m/s². The 120 kW per-motor output entry is a one-hour rating. None establishes a whole-train wheel-force/power envelope. The 826-passenger scenario has a derived actual mass of 213,790 kg but no verified acceleration curve for that load.

Train length becomes necessary for distributed grade forces, stopping-reference offsets and full-train clearance of restrictions. Wheel radius, gear ratio and motor torque are not separately required when wheel force is already specified; adding them without evidence creates redundant unknowns.

## Mathematical model

The governing equation is `m_eff dv/dt = F_T - F_B - R(v) - m g dh/dx`, with `dx/dt = v`. Traction has a constant-force region followed by a constant-wheel-power region; resistance is `A + Bv + Cv²`; coast sets traction and brake commands to zero. Gravity is signed, so downhill coast may accelerate. Braking is a nonnegative wheel-force magnitude, distinct from requested net deceleration.

The [model contract](model-contract.md) defines signs, units, endpoint handling, backward braking limits and mechanical-energy closure. This is the project's approximation rather than a recovered OEM model. Background references include [Tian et al. on DC railway energy evaluation](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-est.2015.0025) and [Heineken et al. on energy-loss modelling](https://link.springer.com/article/10.1007/s40534-023-00322-4). Electrical conversion needs a declared boundary, auxiliaries, losses and actually accepted regeneration before electrical savings can be discussed.

## First development milestone

M1 is a reproducible synthetic station-to-station mechanics study with traceable inputs, a numerical trajectory, mechanical work, analytical verification, constraint checks and sensitivity tests. An implementation that passes these checks may be described as numerically verified under its assumptions. Real-route calibration and operational optimization remain separate gates.

| Acceptance check | Numerical target |
| --- | --- |
| Provenance and units | Active inputs have SI units and evidence status; required null values cannot silently become defaults. |
| Analytical motion | Reproduce all five independent fixtures within 0.1% for nonzero reference quantities. Include constant force, a stop between steps, resistance coast, downhill energy exchange and constant power. |
| Capability | Traction and service-brake envelopes within 1 N; traction power within 0.1%; mutually exclusive traction and braking. Resolve force/power transition. |
| Route constraints | Local speed excess <= 0.05 m/s; arrival error <= 0.5 m and speed magnitude <= 0.05 m/s. Include a lower limit and a short trip that never reaches top speed. |
| Mechanical work | Residual <= 0.1% of max(traction work, brake work, resistance work, abs(delta K), abs(delta U), 1 kJ). Check grade transitions and stops. |
| Numerical convergence | Refine replay and planning resolution/tolerances; travel time and nontrivial work totals change by < 0.5%, retaining endpoint and speed constraints. |
| Feasibility | Reject insufficient starting force, insufficient braking, excessive initial speed, premature stops and exceeded time limits. |
| Reproducibility and sensitivity | Identical inputs/code/settings reproduce results; examine passenger load, resistance, traction force, wheel power, braking, rotating mass and geometry. Arbitrary stress ranges are not confidence intervals. |
| Physical validation | Pending independent applicable observations. Numerical success is not evidence of a particular real-world accuracy percentage. |

## Assumptions to challenge next

- Published acceleration cannot be imposed at every speed: the conditional 826-passenger screening case with 10% tare rotating allowance would need 6.639 MW at 80 km/h before resistance. This is hypothetical required power, not installed power.
- Flat track can conceal material energy: the same actual mass needs 5.824 kWh for a 10 m climb. Maximum grade cannot replace a profile; zero net height change does not imply unchanged motion.
- Capacity is not occupancy; specification age, refurbishments, wheel wear and vehicle generations affect applicability.
- Trip time alone cannot uniquely identify traction, resistance, mass and driving policy. Coast data require known grade, mass and control state.
- Longer travel time can trivially reduce traction demand. Future energy comparisons need equivalent trip constraints and auxiliary accounting; removed brake work is not accepted electrical recovery.

The next evidence priority is one coherent vehicle capability dataset and one direction's as-built profile, followed by independent trajectories. See the [unsent data request](research/data-request-draft.md).
