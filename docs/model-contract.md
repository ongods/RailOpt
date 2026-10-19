# Mathematical model and numerical method

Version 3; documented 18 October 2026. This is the implemented reduction, not an OEM model. See the [experiments](experiments.md), [evidence](research/evidence.md) and [verification](verification.md).

## Boundary and notation

One forward-moving point train has constant mass within a run. Use SI units internally. Historical specifications are in [the vehicle reference](../data/reference/lrt2-vehicle.json); hypothetical inputs belong in separate [scenarios](../data/scenarios/synthetic-1km.json). Missing essential physical inputs must not become silent defaults.

| Symbol | Meaning | Unit |
| --- | --- | --- |
| $x,t,v$ | Along-track position, time, forward speed | $\mathrm m,\mathrm s,\mathrm{m\,s^{-1}}$ |
| $h(x)$ | Rail elevation | $\mathrm m$ |
| $m_0,N,m_{\mathrm p}$ | Tare mass, passenger count, mass per passenger | $\mathrm{kg},1,\mathrm{kg}$ |
| $m_{\mathrm{rot}},m_{\mathrm{eff}}$ | Equivalent rotating mass, effective inertial mass | $\mathrm{kg}$ |
| $F_{\mathrm T},F_{\mathrm B}$ | Nonnegative wheel traction and brake forces | $\mathrm N$ |
| $P_{\mathrm{w},\max}$ | Maximum mechanical wheel traction power | $\mathrm W$ |
| $u_{\mathrm T},u_{\mathrm B}$ | Traction and braking commands | $1$ |
| $W_{\mathrm T},W_{\mathrm B},W_{\mathrm R}$ | Traction work, brake work removed, resistance loss | $\mathrm J$ |

The historical acceleration/service-brake anchors apply to AW3 loading. The $120\,\mathrm{kW}$ entry is a one-hour per-motor output rating. These do not establish aggregate wheel power or full force curves. Emergency ratings and proposed extension drawings are not active service-brake or route inputs.

## Forces and motion

For $v>0$,

$$
\begin{aligned}
m&=m_0+Nm_{\mathrm p},\\
m_{\mathrm{eff}}&=m+m_{\mathrm{rot}},\\
\frac{dx}{dt}&=v,\\
m_{\mathrm{eff}}\frac{dv}{dt}
&=F_{\mathrm T}-F_{\mathrm B}-R(v)-F_{\mathrm{extra}}(x,v)-mg\frac{dh}{dx},\\
R(v)&=A+Bv+Cv^2.
\end{aligned}
$$

Gravity uses actual mass $m$; inertia and kinetic energy use $m_{\mathrm{eff}}$. Whole-train Davis units are $[A]=\mathrm N$, $[B]=\mathrm{N\,s\,m^{-1}}$ and $[C]=\mathrm{N\,s^2\,m^{-2}}$. Coefficients must be nonnegative; do not add aerodynamic drag already represented by $C$.

For conventional grade $i$ (rise divided by horizontal run),

$$
\frac{dh}{dx}=\sin\theta=\frac{i}{\sqrt{1+i^2}}.
$$

Divide percentage grade by $100$ first. Use the same continuous, piecewise-linear rail-height profile for force and potential energy. Uphill slope is positive; downhill coast can accelerate. Point-train geometry cannot resolve distributed grade forces, stopping-reference offsets or full-train clearance of restrictions.

For enabled traction, $P_{\mathrm{w},\max}>0$:

$$
F_{\mathrm T,\max}(v)=
\begin{cases}
F_0,&v=0,\\
\min\!\left(F_0,\dfrac{P_{\mathrm{w},\max}}{v}\right),&v>0.
\end{cases}
$$

$$
\begin{aligned}
F_{\mathrm T}&=u_{\mathrm T}F_{\mathrm T,\max}(v),&
0&\le u_{\mathrm T}\le1,\\
F_{\mathrm B}&=u_{\mathrm B}F_{\mathrm B,\max},&
0&\le u_{\mathrm B}\le1.
\end{aligned}
$$

Here $F_0$ is low-speed wheel-force capability. The transition speed is $v_\ast=P_{\mathrm{w},\max}/F_0$ when both limits are positive. Zero configured power disables traction, including at rest; never evaluate power divided by zero.

The implementation assumes constant whole-train service-brake capability $F_{\mathrm B,\max}$, no separate curve/tunnel resistance ($F_{\mathrm{extra}}=0$), and no explicit adhesion cap. Load-compensation laws, brake blending, actuation delay and jerk limits remain unresolved. Varying passenger load changes mass, not an inferred fleet-specific brake law.

Traction and braking commands are exclusive: $u_{\mathrm T}u_{\mathrm B}=0$. Cruise balances resistance and grade within capability; coast sets both commands to zero. Requested net deceleration $b>0$ requires

$$
F_{\mathrm B,\mathrm{req}}
=m_{\mathrm{eff}}b-R(v)-F_{\mathrm{extra}}(x,v)-mg\frac{dh}{dx}.
$$

This is demand, not capability. Reject excessive demand. Negative demand means coast already slows faster than requested, so maintaining that exact deceleration would require traction. Emergency ratings must not substitute for service braking.

## Numerical integration and stopping

The time-domain state is

$$
\mathbf y=(x,v,W_{\mathrm T},W_{\mathrm B},W_{\mathrm R})^{\mathsf T}.
$$

Use SciPy `solve_ivp` with DOP853. Defaults are relative tolerance $10^{-9}$; absolute tolerances $10^{-8}\,\mathrm m$, $10^{-9}\,\mathrm{m\,s^{-1}}$ and $10^{-3}\,\mathrm J$; and maximum time step $0.25\,\mathrm s$. [Solver documentation](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.integrate.solve_ivp.html) describes tolerance/event semantics.

Resolve the force/power transition as an event and restart. Replay also restarts at grade, speed-limit and control boundaries. Terminate at the first downward zero-speed event; retain raw position, speed and work rather than clipping overshoot. RK trial stages use a nonnegative evaluation speed only to locate the event; stored trajectories are not repaired. Signed root roundoff around $10^{-14}\,\mathrm{m\,s^{-1}}$ is tolerated.

Departure requires positive forward net force. Explicit hold requires sufficient service-brake reaction against gravity and does no mechanical work; a separate breakaway-resistance law is absent. The terminal brake sample is the one-sided pre-hold state. Holding/dwell intervals are not automatically appended; reverse travel is outside scope.

Planning uses squared speed to avoid dividing by speed at a stopped endpoint:

$$
w=v^2,\qquad
\frac{dw}{dx}=\frac{2F_{\mathrm{net}}}{m_{\mathrm{eff}}},
\qquad w(L)=0,
$$

where $L$ is destination distance and $F_{\mathrm{net}}$ is the same signed force balance as above. Integrate maximum service braking backward from rest, capped by local speed limits. Integrate forward traction/requested coast until it meets that envelope, then follow it using braking or force-balanced cruise. Replay the phase locations independently in time; final stopping error remains measurable.

Spatial integration uses DOP853, a $5\,\mathrm m$ maximum step and squared-speed absolute floor $10^{-9}\,\mathrm{m^2\,s^{-2}}$. Refine both spatial and temporal settings in verification. The conservative planner requires positive net service-braking deceleration even at zero speed on every grade; it rejects steeper downhills rather than claiming general feasibility. Coasting is subordinate to constraints and is not an optimized policy. `maximum_time_s` is a timeout, not fixed-arrival-time optimization.

## Mechanical energy

Integrate work with motion:

$$
\begin{aligned}
\frac{dW_{\mathrm T}}{dt}&=F_{\mathrm T}v,\\
\frac{dW_{\mathrm B}}{dt}&=F_{\mathrm B}v,\\
\frac{dW_{\mathrm R}}{dt}&=\bigl(R+F_{\mathrm{extra}}\bigr)v,\\
K&=\frac12m_{\mathrm{eff}}v^2,\qquad U=mgh,\\
\varepsilon_E
&=W_{\mathrm T}-W_{\mathrm B}-W_{\mathrm R}-\Delta K-\Delta U.
\end{aligned}
$$

Here $\Delta$ means change from the initial state. Energy converts through $1\,\mathrm{kWh}=3.6\times10^6\,\mathrm J$. The residual $\varepsilon_E$ should remain within the [acceptance tolerance](verification.md#acceptance-criteria). Mechanical brake work is not regenerated electricity.

## Optional train-terminal electrical boundary

The electrical layer in `railway/electrical.py` accounts for one train's onboard
traction conversion, regenerative conversion, friction braking and constant
auxiliary consumption during the simulated interval. Imported and exported energy
cross the train's electrical terminals. Net supply energy is import minus export;
it is not substation energy. Feeder/substation losses, supply-voltage dynamics,
other trains, storage, rheostatic braking and unsimulated dwell are excluded.
The model does not predict network receptivity. Electrical parameters do not
change requested wheel braking or traction capability.

All seven parameters must be explicitly provided if a scenario has an `electrical`
section; each needs its own evidence entry. Legacy mechanics-only scenarios remain
supported. The synthetic example's values are arbitrary hypothetical inputs, not
estimated LRT-2 efficiencies, loads or regenerative ratings.

| Parameter | Meaning and bounds | Unit |
| --- | --- | --- |
| `motoring_efficiency`, $\eta_T$ | Terminal-to-wheel conversion, $0<\eta_T\le1$ | 1 |
| `regenerative_efficiency`, $\eta_B$ | Wheel-to-electrical-bus conversion, $0\le\eta_B\le1$ | 1 |
| `auxiliary_power_w`, $P_A$ | Constant electrical bus consumption | W |
| `regenerative_force_n`, $F_G$ | Maximum regenerative wheel force | N |
| `regenerative_wheel_power_w`, $P_G$ | Maximum regenerative mechanical wheel power | W |
| `regenerative_acceptance_fraction`, $r$ | Declared fraction of potential generation enabled for reuse/export, $0\le r\le1$ | 1 |
| `maximum_export_power_w`, $P_X$ | Electrical terminal export ceiling | W |

Power and force limits are finite and nonnegative. For nonnegative speed and the
actual requested brake force $F_B$, define counterfactual electrical capability
$Q$, actual accepted generation $P_C$, and actual recovered wheel power $P_W$:

$$
\begin{aligned}
Q &= \eta_B \min\!\left(F_B v,\; F_G v,\; P_G\right), \\
P_C &= \min\!\left(rQ,\; P_A + P_X\right), \\
P_W &= \begin{cases}
\dfrac{P_C}{\eta_B}, & \eta_B > 0, \\
0, & \eta_B = 0,
\end{cases} \\
P_{\mathrm{reuse}} &= \min\!\left(P_C,\; P_A\right), \\
P_{\mathrm{export}} &= P_C - P_{\mathrm{reuse}}, \\
P_{\mathrm{import}} &= \frac{F_T v}{\eta_T} + P_A - P_{\mathrm{reuse}}, \\
P_{\mathrm{net}} &= P_{\mathrm{import}} - P_{\mathrm{export}}.
\end{aligned}
$$

$r$ is a scenario acceptance assumption applied before allocating auxiliary reuse
and export; zero disables all actual regeneration. With $r=1$ and zero export
capacity, auxiliaries alone can still accept generation. There is no low-speed
cutoff in this first approximation: force-limited recovery tends to zero as speed
tends to zero. No actual regeneration occurs at rest, with zero conversion
efficiency, or with zero regenerative force or power capability. Acceptance
curtailment sends remaining wheel-brake demand to friction, rather than generating
unusable electricity. Thus actual generated electricity is entirely accepted;
potential generation is reported separately and never deducted from supply draw.

The corresponding losses are nonnegative:

$$
\begin{aligned}
P_{\mathrm{motoring\,loss}} &= \frac{F_T v}{\eta_T} - F_T v, \\
P_{\mathrm{regenerative\,loss}} &= P_W - P_C, \\
P_{\mathrm{friction}} &= F_B v - P_W.
\end{aligned}
$$

Electrical powers follow the same exclusive traction/braking commands as the
mechanical model, including downhill braking during cruise. Auxiliary reuse is
deducted from import once; only surplus generation is exported. The full boundary
balance is

$$
\begin{aligned}
E_{\mathrm{net}} ={}& \Delta K + \Delta U + W_{\mathrm R} + W_{\mathrm{friction}} \\
&+ E_{\mathrm{motoring\,loss}} + E_{\mathrm{regenerative\,loss}} + E_{\mathrm{auxiliary}}.
\end{aligned}
$$

The numerical method appends three cumulative integrals (potential generation,
actual recovered wheel work, auxiliary reuse) to the same time-domain ODE. The
existing five mechanical state rows and mechanics-only interfaces are retained.
Integrals use the work absolute tolerance and restart at all existing phase
boundaries; continuous force/power and acceptance kinks are handled adaptively.
All other accounts follow from those integrals, mechanical work and elapsed time.
Holding can consume auxiliary electricity with zero wheel work. Station dwell is
included only when an explicit holding interval is simulated.

Outputs distinguish cumulative potential generation, actual generation, accepted
generation, recovered wheel work, conversion losses, friction work, auxiliaries,
auxiliary reuse, import, export and net supply energy in joules. Actual generated
and accepted energy coincide under this friction-substitution policy. The
electrical bookkeeping residual is

$$
\varepsilon_{\mathrm{elec}} = E_{\mathrm{net}} -
\left(E_{\mathrm{motoring}} + E_{\mathrm{auxiliary}} - E_{\mathrm{accepted}}\right).
$$

This is an algebraic consistency check, not independent validation.
Runtime acceptance rejects nonfinite accounts and material negative losses,
imports or exports, excessive accepted generation, reuse or export, and excessive
bookkeeping residual. It uses a 0.1% energy criterion with a 1 kJ scale floor,
retaining raw numerical roundoff instead of clipping the accounts.
Combined with the mechanical residual, analytical conversion/limited-braking
tests and electrical refinement checks establish numerical verification. They do
not establish that the hypothetical electrical inputs describe a real train.

## Outputs and acceptance

The optional scenario `sensitivity` section declares its scope, baseline-context
`electrical` sweeps, `regenerative` sweeps and explicit
`regenerative_reference_acceptance_fraction`. Each sweep maps electrical parameter
names to nonempty lists of values validated against the same physical bounds as
ordinary inputs. It requires its own evidence entry. Regenerative sweeps use the
named receptive reference so baseline zero acceptance does not hide their effect.
Exports include actual parameters, reference identifiers and changes; ranges are
selected stresses, not measured uncertainty. See [electrical sensitivity](experiments.md#electrical-sensitivity).

Export SI trajectories, controls, forces, wheel power, cumulative work and residual, with complete configuration/evidence status. Run identifiers hash configuration, module contents and software versions. Adaptive samples include events/switches; a switch uses the new phase's one-sided forces. Generated files stay in ignored `results/`; figures must identify synthetic inputs.

## Coasting benchmark protocol

`python -m railway.benchmark` loads a declared experiment from
`data/experiments/coasting-benchmark.json` and the referenced scenario. It always
includes no requested coast and the scenario's existing control, then sweeps the
listed switch positions. Only `coast_from_m` changes; vehicle, route, electrical
parameters, initial state and timeout remain fixed. The objective pair is journey
time and net train-terminal electrical energy, including auxiliaries over the
actual journey. No target arrival time or equal-time savings objective is imposed.

Each completed time replay receives a separate sample/phase audit for state,
endpoint, speed, force/power and work bounds, regenerative accounting and energy
closure. Mechanical closure uses actual mass for potential energy and effective
mass for kinetic energy. Full train-boundary closure separately compares terminal
net draw against changes in kinetic/potential energy, resistance, friction,
conversion losses and auxiliary consumption. Endpoint/speed/force/power/balance
tolerances follow the existing mechanical verification criteria. The audit retains
raw residuals and samples; it does not clip them to pass constraints or prove
continuous-time satisfaction between accepted samples.

Only explicit `InfeasibleRun` exceptions are recorded as `infeasible_policy` with
their original reason and no fabricated trip time/energy. Other solver/software
errors propagate. A completed replay failing the separate audit is `audit_failed`.
Reference controls, sampled fastest/slowest/minimum-energy cases, the largest
rejected switch and explicit refinement probes are rerun with half the time and
planning steps and tenfold tighter tolerances. Selected feasible cases must pass
their refined audit and retain time/work/electrical totals within 0.5%; rejected
probes must remain rejected. Disagreement is `refinement_failed`, excluded from
the frontier and reported with a nonzero CLI exit status. The rejection boundary
is sampled rather than solved continuously.

For a feasible sample $B$, another sample $A$ is a dominance witness when

$$
\begin{gathered}
T_A \le T_B + \delta_t \quad\text{and}\quad E_A \le E_B + \delta_E, \\
\text{with}\quad
\left(T_A < T_B - \delta_t \quad\text{or}\quad E_A < E_B - \delta_E\right).
\end{gathered}
$$

The declared $\delta_t=0.01\,\mathrm s$ and $\delta_E=100\,\mathrm J$ bands
are numerical tie tolerances, not measurement uncertainties or timetable
allowances. Ties are retained. Frontier membership applies only to the sampled
one-switch policies; connecting lines in the plot are guides, not new feasible
profiles or a global optimal-control solution.

The command exports SI CSV/JSON records, a standalone feasibility Markdown report
and PNG/SVG figures identifying the benchmark hash. Full experiment/scenario
configuration, source-module hashes, historical reference hash and software
versions accompany the results. Matplotlib is pinned in `requirements.txt`;
its default plotting cache is within ignored `.cache/matplotlib/`.
See the [coasting experiment](experiments.md#coasting-tradeoff).

## Commanded cruise-speed ceiling

The optional control `cruise_speed_cap_mps` is a positive finite command in m/s.
Omission or `null` preserves the original policy. When set, the backward braking
envelope uses the ceiling

$$
v_{\mathrm{command}}(x) = \min\!\left(v_{\mathrm{limit}}(x),\; v_{\mathrm{cap}}\right),
$$

where $v_{\mathrm{limit}}(x)$ is the physical route limit and $v_{\mathrm{cap}}$ is
the commanded cruise ceiling. This applies throughout the run. Route limits
remain unchanged and are audited separately from the command. The same ceiling
applies after a coast request: downhill acceleration can trigger cruise braking
to stay on the ceiling. This command does not change available force or power.
An initial speed above the command is explicitly rejected as `InfeasibleRun`;
the initial state is never clipped. Short trips need not attain the ceiling.

Failed or nonfinite spatial integration raises `RuntimeError`, as time integration
does. Only explicit policy/capability rejections use `InfeasibleRun`.

## Matched-time experiment

`python -m railway.matched` loads `data/experiments/matched-time.json`. It minimizes
net train-terminal energy including actual-duration auxiliaries, over a commanded
cruise ceiling and one coast position. The reference has no requested coast and
uses the lowest-energy feasible tested ceiling. Both profiles use identical
physical/electrical inputs, distance, rest-to-rest endpoints and the declared
arrival constraint

$$
\left\lvert T - T_{\mathrm{target}}\right\rvert \le \delta_T,
$$

where $T$ is actual arrival time, $T_{\mathrm{target}}$ is the target and $\delta_T$
is the arrival tolerance. `maximum_time_s` remains a
separate timeout; waiting is never added to match arrival times.

The default synthetic target is $85.0\pm0.1\,\mathrm s$, not a railway timetable. A bounded
two-dimensional grid samples caps from 12 to 20 m/s and coast switches from 100
to 900 m. Every observed adjacent cap/time crossing is bisected with explicit
simulation at each new point, without a global monotonicity assumption. A second
search halves both grid spacings over the same bounds. A 100 kJ maximum change in
each selected profile's energy and unchanged ranking define empirical search
stability. These criteria do not establish global optimality or locate every
possible crossing.

Each sampled replay passes the independent benchmark audit before arrival
acceptance. Selected controls are JSON serialized and independently replayed, then
rerun with half the time/planning steps and tenfold tighter tolerances. Both
replays must pass the audit and arrival constraint, with less than 0.5% change in
time/work/electrical totals. Search-grid stability is separate from this numerical
integration check. Reports retain all samples, statuses, actual arrival errors
and time difference, configuration, bounds, software versions and source hashes.
A missing feasible pair is reported only as failure within the tested bounds;
the CLI exits nonzero for an unverified or absent comparison.

The nine auxiliary-power/acceptance combinations (50/100/150 kW and 0/0.5/1)
replay the fixed nominal controls and repeat audit/arrival/refinement checks.
Neither strategy is retuned: this tests ranking robustness of that pair, rather
than best achievable performance under changed assumptions. Ranking uses the
larger of 100 J and the sum of both numerical energy-refinement changes. Ranges
are hypothetical choices, not confidence intervals. No new fleet data are assumed.

## Saved-run schematic replay

The standard exporter writes `trajectory.csv`, `run.json` and a trajectory SHA-256.
Electrical exports also include instantaneous `regenerative_accepted_power_w`.
The saved-output viewer interpolates states/accounts and holds discontinuous
controls/forces from one side without rerunning physics. Data validation, event
synchronization, paired playback and recording are documented in [replay](replay.md).
Playback changes no simulated duration or energy and does not establish physical
validation.
