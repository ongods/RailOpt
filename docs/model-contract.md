# Mathematical model and numerical method

Version 2; documented 17 October 2026. This is the implemented reduction, not an OEM model. See the [README findings](../README.md#findings), [evidence](research/evidence.md) and [verification](verification.md).

## Boundary and notation

One forward-moving point train has constant mass within a run. Use SI units internally. Historical specifications are in [the vehicle reference](../data/reference/lrt2-2011.json); hypothetical inputs belong in separate [scenarios](../data/scenarios/synthetic-1km.json). Missing essential physical inputs must not become silent defaults.

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

Here $\Delta$ means change from the initial state. Energy converts through $1\,\mathrm{kWh}=3.6\times10^6\,\mathrm J$. The residual $\varepsilon_E$ should remain within the [acceptance tolerance](phase-1-plan.md). Mechanical brake work is not regenerated electricity; conversion, auxiliaries and accepted export require a separate electrical boundary model.

## Outputs and acceptance

Export SI trajectories, controls, forces, wheel power, cumulative work and residual, with complete configuration/evidence status. Run identifiers hash configuration, module contents and software versions. Adaptive samples include events/switches; a switch uses the new phase's one-sided forces. Generated files stay in ignored `results/`; figures must identify synthetic inputs.

The [test suite](../tests/test_dynamics.py) checks five independent analytical fixtures, capability/route constraints, stop events, infeasibility, work closure and refinement. Ideal fixtures verify equation reductions; hypothetical scenarios verify numerical behaviour. Neither calibrates the fleet. Physical validation requires independent applicable observations.
