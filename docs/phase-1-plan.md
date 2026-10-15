# Philippine Railway Dynamics and Energy Optimization: Phase 1

Research date: 15 October 2026. Status: proposed model and requirements; implementation has not begun.

## Decision and scope

Use the original LRT-2 four-car rolling-stock configuration documented in the 2011 JICA preparatory study as the provisional reference. Freeze the reference year and configuration; do not describe this as a calibrated representation of the present fleet. Choose an actual interstation section only after its track distance and vertical profile can be documented. Until then, use an explicitly synthetic route with a Philippine reference vehicle.

The initial research question is: **Can a transparent, physically consistent longitudinal model reproduce basic train motion and expose how uncertain vehicle and route inputs affect travel time and mechanical energy?**

Phase 1 covers one train, one direction, fixed load within a run, prescribed speed restrictions, traction, cruise, coasting, service braking, and mechanical energy accounting. Electrical energy is a separate estimate conditional on additional assumptions. Optimization, network simulation, signalling interactions, detailed traction circuits, suspension dynamics, adhesion transients, and a user interface are later work.

## Target assessment

These rankings reflect the primary public sources located in this research pass, not proof that other public documents do not exist.

| Target | Evidence available | Main qualification | Phase 1 suitability |
| --- | --- | --- | --- |
| LRT-2 | JICA 2011 study, especially Tables 3.6-1 and 3.6-2, links configuration, loading mass, performance and propulsion; operations and geometry context also appear. | Historical design/specification information does not establish current force curves or measured energy. | First choice: useful inputs occur together, reducing cross-fleet mixing. |
| LRT-1 | JICA 2013 Volume 1 appendix, Table 3-1, gives separate specifications for three historical generations. | Select one generation and year; a generic LRT-1 vehicle would mix distinct trains. | Close second, especially a documented third-generation train. |
| MRT-3 | DOTr system description and JICA rehabilitation reporting give operating context; historical JICA comparison tables provide broad specifications. | A 2019 successful FOI request says specifications were emailed; that page does not expose those values. | Feasible, but more parameter verification is needed in this evidence set. |

Sources: [LRT-2 study](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf), [LRT-1 appendix](https://openjicareport.jica.go.jp/pdf/12126629_02.pdf), [DOTr MRT-3 description](https://www.dotrmrt3.gov.ph/about-us), [historical JICA comparison, Table 2.1](https://openjicareport.jica.go.jp/pdf/12247656_01.pdf#page=88), and [DOTr FOI response](https://www.foi.gov.ph/requests/specifications-of-the-mrt-3-trains-currently-being-used-and-48-dalian-trains-delivered-from-china/).

For an MRT-3 implementation, choose a specific vehicle class and consist rather than combining Czech and Dalian specifications. Keep vehicle design speed distinct from the operating limit for the chosen period. JICA's [2026 rehabilitation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2025/LoanAgreementSign-MRT3.html) reports 60 km/h after rehabilitation; historical comparison tables list 65 km/h. They must not be treated as interchangeable route permissions.

LRT-1 is also worth revisiting if calibration data become available: JICA's [2026 energy-conservation announcement](https://www.jica.go.jp/english/overseas/philippine/information/press/2026/LRMC_TA_EnergyConservation.html) is a lead to operational analysis, not a downloadable calibration dataset.

## Evidence and parameter policy

Each parameter needs a definition, SI unit, value or unresolved status, vehicle/route/year applicability, source URL and table/page, original unit, conversion, uncertainty treatment, and effect on permitted claims. See [parameter-register.csv](parameter-register.csv).

Use four statuses:

- **Published specification:** reported by a primary source; not automatically a measured operating value.
- **Derived:** calculated transparently from identified inputs.
- **Assumed:** selected for a scenario or borrowed from a documented comparable vehicle; never relabelled as local measurements.
- **Unresolved:** necessary input not established yet. No hidden defaults.

Initial LRT-2 anchors are a 160.10 t empty four-car train; a report convention of 65 kg per passenger; an 80 km/h maximum; and 4.68 km/h/s acceleration and average deceleration entries, equivalent to 1.30 m/s². These are specification anchors, not a speed-dependent capability curve. The report's AW2 passenger counts differ between tables (1,030 and 1,026); AW4 includes a structural dynamic-load allowance and is not an operating mass. Source: [JICA Tables 3.6-1 and 3.6-2, PDF pages 159–160](https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf#page=159).

A useful explicit reference scenario is 826 passengers at that report's mass convention: m = 160,100 + 826 × 65 = 213,790 kg. This scenario does not assert observed occupancy. Preserve the passenger count and per-person mass separately for sensitivity analysis. Avoid the inconsistent AW2 row for the baseline.

Before freezing numerical inputs, visually check the cited PDF tables against their text extraction and reconcile critical conflicts. Web PDF rendering was unreliable during this research; transcriptions remain subject to that check. Older reports also contain proposals: retain only data explicitly applicable to the selected existing train and route.

## Minimum required inputs

| Input | Why needed | Public evidence versus remaining work |
| --- | --- | --- |
| Train composition and empty mass m0 | Establish consistent whole-train forces and energy | Published for the reference configuration; check the meaning of mass and included equipment. |
| Passenger count N and passenger/luggage mass mp | m = m0 + N mp | Published capacity is a bound/scenario convention; actual trip occupancy is an assumption without observations. |
| Equivalent rotating mass m_rot | Rotational kinetic energy and inertia | Assume or derive from inertias; not established for these fleets. |
| Wheel tractive force versus speed | Determines attainable acceleration | Full curves were not located. Need F0 and wheel power P_w,max for the approximation below. A motor rating alone is insufficient. |
| Service-brake force envelope and command | Determines stopping distance | Nominal deceleration is published; load dependence, blending, delay and full force curve remain unresolved. |
| Running resistance R(v) | Coasting and energy losses | Fleet-specific Davis coefficients were not located. Use documented comparable coefficients or bounded assumptions pending calibration. |
| Track distance, stop positions, grade profile | Defines geometry and gravity | Reports/maps provide leads; obtain track chainage and vertical profile for the chosen section. Ground elevation is not rail elevation. |
| Local permissible speed profile | Constrains trajectory | Published top speed does not establish every local limit. Mark reconstructed limits as assumed. |
| Curvature/tunnel information where relevant | Additional resistance and speed restrictions | Obtain for the selected section or declare the omission and test its influence. |
| Powered/braked supported mass and adhesion, if explicit adhesion caps are used | Bounds transferable wheel forces | Needed only when those caps are modelled separately; otherwise document the assumed non-slipping capability envelope. |
| Initial/end conditions and control policy | Makes a reproducible run | Chosen scenario: start and stop at rest; specified switches or controller. |
| Efficiency, auxiliary power and regeneration limits | Electrical-energy estimates only | Not established for the reference train; optional scenario assumptions. |
| Independent trajectories and energy observations | Physical validation | No suitable time-resolved public dataset established in this pass. Procurement specifications and annual totals are not equivalent. |

Train length is needed for finite-length treatment of grades or speed restrictions; with a short point-mass approximation its omission must be stated. Wheel radius, gear ratio, individual motor torque and frontal area are not separately essential if wheel force and Davis resistance are already specified. Adding them without independent evidence can create redundant unknowns.

## Minimal mathematical model

The proposed reduction follows longitudinal force balance and a Davis resistance formulation used in rail energy studies. See [Tian et al., DC railway energy evaluation](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-est.2015.0025) for the separation between train motion and electrical-network energy, and [Heineken et al., energy-loss modelling](https://link.springer.com/article/10.1007/s40534-023-00322-4) for the consequences of simplified conversion losses. The equations below are the project's proposed approximation, not a recovered OEM model.

Use SI units internally: x [m], t [s], v [m/s], mass [kg], force [N], power [W], energy [J]. Divide joules by 3.6 million for kWh.

### Mass, forces and signs

For forward travel v > 0:

    m = m0 + N mp
    m_eff = m + m_rot
    dx/dt = v
    m_eff dv/dt = F_T - F_B - R(v) - F_C(x,v) - m g sin(theta(x))
    R(v) = A + B v + C v²

F_T and F_B are nonnegative traction and braking force magnitudes. F_C is optional extra curve/tunnel resistance not already represented in R. Positive theta is uphill in the direction of travel. Define theta from a consistent rail height profile h(x), with dh/dx = sin(theta) when x is distance along the track. For small grades, the gravity term is approximately m g i where i is signed grade as a fraction, not percent.

Use actual mass for gravity and effective mass for acceleration. A simple rotating-mass assumption is m_rot = lambda0 m0, constant during a run; it does not increase with passenger mass. A finite-length refinement averages gravity over the train's mass distribution. At sharp grade changes this can matter even with a one-dimensional model.

A has units N, B has units N·s/m, C has units N·s²/m² for this whole-train convention. Do not mix these with coefficients specified per tonne or for km/h. Do not add aerodynamic drag again if C already includes it. Apply resistance opposite motion; the forward-only formula is not a standstill law.

### Traction and cruising

    F_T,max(v) = min(F0, P_w,max / v)           for v > 0
    F_T,max(0) = F0
    F_T = u_T F_T,max(v),  0 <= u_T <= 1

Optionally also cap by mu_T m_driven g cos(theta). P_w,max means mechanical power at the wheels, not electrical line power. This approximation gives a constant-force region followed by a constant-power region. Its transition speed is P_w,max/F0.

If the reference load, test speed and resistance are known, a low-speed acceleration specification can constrain F0 through F0 approximately equal to m_eff a_ref + R(v_ref) + grade force. Without those conditions it only provides a plausibility anchor. Do not force published maximum acceleration to persist at every speed or every load.

Cruising requires the controller to balance resistance and grade within available traction/braking limits. A speed cap is enforced by control and braking anticipation, not by simply clipping velocity after a numerical step. If available force cannot sustain the requested speed uphill, the model must slow down.

### Coasting and braking

Coasting sets F_T = F_B = 0. Speed falls on a level track with positive resistance; it can increase downhill. Coasting is not a prescribed constant negative acceleration.

    F_B = u_B F_B,max(v,m),  0 <= u_B <= 1

Start with a documented finite service-brake envelope. An assumed load-compensated deceleration command is acceptable only if the corresponding force remains within that envelope. Distinguish service braking from emergency ratings. Baseline traction and braking commands are mutually exclusive.

With positive downhill force, stopping requires enough brake force to overcome gravity as well as remove kinetic energy. Generate a backward braking envelope from each stopping point or lower speed restriction using the same grade and force model. The flat-track expression v²/(2b) is only an analytical test case.

Handle zero-speed arrival as an event, land at rest, then enter a holding state. Do not allow resistance or overshooting integration steps to reverse the train. Holding on a slope requires brake force. If available braking cannot stop the train in the distance, report an infeasible run instead of snapping to the station. Acceleration discontinuities are allowed in this first model; add actuation dynamics and jerk limits before making ride-comfort claims.

### Mechanical and electrical energy

    W_T = integral(F_T v dt)
    W_B = integral(F_B v dt)
    W_R = integral((R + F_C) v dt)
    K = 0.5 m_eff v²
    U = m g h
    W_T - W_B - W_R = delta K + delta U

Mass is constant within a segment. Evaluate each differently loaded segment separately. Log braking energy as removed mechanical work; do not subtract it from traction work and call the result electricity consumption.

Optional vehicle electrical-boundary estimate:

    P_in = F_T v / eta_T + P_aux
    0 <= F_reg <= F_B
    P_return = q(t) eta_R F_reg v
    E_net = integral((P_in - P_return) dt)

eta_T and eta_R describe conversion to/from the same declared vehicle electrical boundary; q is network acceptance between zero and one. F_reg also needs a speed-dependent regenerative force/power envelope and low-speed fade-out. The remainder of braking must be dissipated through friction/rheostatic equipment. Unaccepted regenerative power is dissipated, not deleted from the mechanical balance.

Default reporting should give wheel traction work, mechanical brake work and resistive losses first. If electrical scenarios are added, show no accepted recovery and an explicitly idealized recovery bound. Actual substation/grid consumption requires network receptivity, losses and interactions with other trains. A single train cannot establish those.

## Assumptions that need to be challenged

1. **A working solver is not a validated Philippine train model.** Analytical tests verify equations and numerics. Physical validation needs independent local observations.
2. **Flat route assumptions can dominate energy errors.** At the reference scenario mass, a 1% grade adds approximately 21 kN; a 10 m climb adds 5.82 kWh of mechanical potential energy. Use grade scenarios while the vertical profile is unknown. Do not distribute a reported maximum grade across an entire interstation run.
3. **Published acceleration is not an OEM traction curve.** A constant acceleration up to top speed implies growing wheel power and can violate installed capability.
4. **Capacity is not occupancy.** Empty, intermediate and crowded load scenarios are needed. Passenger boardings per day do not determine the mass on one segment.
5. **Borrowed resistance is not local calibration.** A complete trip time cannot uniquely identify mass, traction, resistance and driver behaviour. Coasting observations with known grade and load are more informative, though still insufficient if controls are unknown.
6. **Regenerative braking is not guaranteed grid savings.** Keep mechanical energy removed, conversion potential and accepted export separate.
7. **Longer travel time can make a lower-energy result trivial.** Later optimization must compare identical route, load, stops, restrictions and arrival time. Include auxiliary energy when comparing electrical consumption over different durations.
8. **Specification age matters.** Overhauls, modified propulsion, wheel wear, restrictions and different train generations can invalidate an apparent match.

For screening, vary passenger load, resistance, F0, wheel power, braking capability, grade and rotating mass. Assign numeric ranges only with a stated basis. If broad arbitrary perturbations are useful, label them stress tests rather than measured uncertainty or confidence intervals. Recalculate force/power consistency whenever load changes. Do not claim savings robustly if their sign changes within plausible input choices.

## First milestone and acceptance criteria

**Milestone M1: one reproducible station-to-station dynamics and mechanical-energy study, with a traceable parameter file and explicit limits on physical validation.**

Planning allowance: roughly 20–35 focused hours over several part-time weeks, contingent on data access. This is a work estimate, not a promise that a missing vertical profile will become available.

Proceed in this order:

1. Spend an initial 6–10 hours reviewing original tables, fixing vehicle/year/consist, finding a route section, and documenting assumptions. Freeze the parameter register and mathematical conventions before implementing the solver.
2. If track distance or vertical profile remains unavailable, freeze a synthetic approximately 1 km section with declared grade and speed limits. Deliver a vehicle-referenced scenario study, with the real-route validation gate explicitly open.
3. Implement only the numerical core and a small reproducible notebook/script when the model has been reviewed. Run acceleration, cruise, coast and service-braking modes; include a short section where the top speed is never reached.
4. Export x(t), v(t), acceleration, force, wheel power, mode, accumulated mechanical energy, the complete configuration and run identifier. Plot speed against time/distance, force/power against speed/time, and cumulative energy. Report arrival time, stop error, peak speed/force/power and the energy residual.
5. Run analytical, numerical and sensitivity checks. Add an observational comparison only when independent applicable data exist.

Proposed acceptance tolerances below are numerical targets, not statements of real-world accuracy.

| Test | Acceptance criterion |
| --- | --- |
| Provenance and units | Every active input has SI units, applicability and evidence status. A missing required input prevents an unqualified run; no silent defaults. Critical transcribed values have been visually checked or remain explicitly provisional. |
| Constant net force on level track | With resistance and other effects disabled, reproduce v = v0 + Ft/m_eff and x = x0 + v0 t + Ft²/(2m_eff) to 0.1% on nonzero reference quantities. |
| Constant-force stopping | For net deceleration b, reproduce t_stop = v0/b and d_stop = v0²/(2b) to 0.1%; no negative speed. Include an event between integration samples. |
| Coasting and grade sign | Level, positive resistance: speed and K fall. Zero resistance with grade: K + U stays constant. Downhill case can accelerate. A nontrivial zero-net-height profile still changes the trajectory. |
| Traction/brake capability | At every accepted step, force stays within the configured envelope (1 N numerical tolerance), wheel power within its configured traction cap (0.1%), and traction/brake commands are exclusive. Test start from zero and the force/power transition. |
| Speed restrictions and stopping | Respect each local speed cap within 0.05 m/s; arrive within 0.5 m and at <= 0.05 m/s before holding. Include a lower limit before the destination and a run too short to reach top speed. Infeasible cases are explicitly rejected. |
| Mechanical energy closure | Absolute residual <= 0.1% of max(W_T, W_B, W_R, abs(delta K), abs(delta U), 1 kJ), including grade changes and standstill events. Refine numerical settings if necessary. |
| Numerical convergence | Tightening solver tolerances or halving the maximum step changes travel time and nontrivial energy totals by < 0.5%, while retaining stopping and speed-limit tolerances. |
| Reproducibility and sensitivity | Identical configurations reproduce results. Report the effect of load, resistance, power, grade and rotating-mass scenarios; do not assign unsupported probability distributions. |
| Optional electrical accounting | eta_T=eta_R=1, q=1, no auxiliaries and sufficient regenerative capability reproduce wheel energy transfers; q=0 gives no export. Accepted energy never exceeds convertible mechanical brake work. |
| Independent physical validation | If suitable observations exist, set a comparison tolerance from their resolution and variability before fitting. Use held-out runs/segments. Otherwise report 'numerically verified; physical calibration/validation pending'. Do not invent a 5% accuracy claim. |

M1 can be complete as a numerically verified engineering model even if local validation data remain unavailable, provided the claim and deliverable title reflect that limit. It cannot be called a validated digital twin or a measured forecast of line energy use. The next milestone should add a documented real route and independent validation before any operational energy-optimization claims.

## Next evidence to obtain

Prioritize a rail vertical profile and stop-to-stop track distances; an OEM or operator wheel-force/power curve with loading and voltage conditions; service-brake behaviour; resistance/coasting observations; and a measured speed/time trace. For electrical work, seek onboard traction/auxiliary measurements and distinguish imported and exported energy. Requesting access to an operator's data is a possible later action; no requests have been sent.
