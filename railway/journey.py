"""Backward braking limits, forward reachability, and independent time replay.
Planning uses w=v², for which dw/dx=2F_net/m_eff has no division by speed.
Time and work are calculated only by replay through the time-domain ODE.
"""

from bisect import bisect_right
from dataclasses import dataclass
from math import sqrt
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from .electrical import ElectricalEnergy, ElectricalParameters, electrical_energy
from .integration import SegmentResult, Settings, energy_residual_j, integrate_segment
from .physics import Command, G, InfeasibleRun, Vehicle, finite, forces


@dataclass(frozen=True)
class Route:
    # Along-track distance and rail elevation [m]; speed limits start at x=0.
    rail_points_m: tuple[tuple[float, float], ...]
    speed_limits_mps: tuple[tuple[float, float], ...]

    def __post_init__(self):
        if len(self.rail_points_m) < 2 or self.rail_points_m[0][0] != 0:
            raise ValueError("Rail profile needs at least two points and must start at x=0")
        for x, height in self.rail_points_m:
            finite("rail x", x, 0)
            finite("rail height", height)
        for (x0, h0), (x1, h1) in zip(self.rail_points_m, self.rail_points_m[1:]):
            if x1 <= x0 or abs(h1 - h0) >= x1 - x0:
                raise ValueError("Rail distances must increase and abs(dh/ds) must be < 1")
        if not self.speed_limits_mps or self.speed_limits_mps[0][0] != 0:
            raise ValueError("Speed restrictions must start at x=0")
        previous = -1.0
        for x, speed in self.speed_limits_mps:
            finite("speed restriction x", x, 0)
            finite("speed limit", speed, 0)
            if x <= previous or x >= self.length_m or speed == 0:
                raise ValueError("Restriction positions must increase within route; speeds must be positive")
            previous = x

    @property
    def length_m(self) -> float:
        return self.rail_points_m[-1][0]

    def _rail_segment(self, x: float):
        # Linear extension is used only to retain a tiny terminal replay position error.
        i = min(max(bisect_right([p[0] for p in self.rail_points_m], x) - 1, 0), len(self.rail_points_m) - 2)
        return self.rail_points_m[i], self.rail_points_m[i + 1]

    def slope(self, x: float) -> float:
        (x0, h0), (x1, h1) = self._rail_segment(x)
        return (h1 - h0) / (x1 - x0)

    def height_m(self, x: float) -> float:
        (x0, h0), _ = self._rail_segment(x)
        return h0 + (x - x0) * self.slope(x)

    def speed_limit_mps(self, x: float) -> float:
        i = max(bisect_right([p[0] for p in self.speed_limits_mps], x) - 1, 0)
        return self.speed_limits_mps[i][1]


@dataclass
class Phase:
    start_m: float
    end_m: float
    command: Command
    dh_ds: float


@dataclass
class BrakingBand:
    start_m: float
    end_m: float
    squared_speed: Callable[[float], float]
    braking: bool
    dh_ds: float


def _spatial_solve(rhs, start, end, w0, settings, event=None):
    solution = solve_ivp(rhs, (start, end), [w0], method="DOP853", dense_output=True,
                         events=event, rtol=settings.rtol, atol=settings.speed_atol_mps**2 + 1e-9,
                         max_step=settings.planning_step_m)
    if not solution.success or not np.isfinite(solution.y).all() or not np.isfinite(solution.t).all():
        raise RuntimeError(f"Spatial planning failed: {solution.message}")
    return solution


def braking_bands(vehicle: Vehicle, route: Route, settings: Settings,
                  extra_breaks: tuple[float, ...] = (),
                  cruise_speed_cap_mps: float | None = None) -> list[BrakingBand]:
    """Construct a speed-limited maximum-service-braking envelope backward from rest.

    This first planner conservatively requires positive net braking at zero speed
    on every grade. It rejects, rather than claims to solve, steeper downhill cases.
    """
    breaks = sorted({*(x for x, _ in route.rail_points_m),
                     *(x for x, _ in route.speed_limits_mps), *extra_breaks})
    bands = []
    w_right = 0.0
    for left, right in reversed(list(zip(breaks, breaks[1:]))):
        slope = route.slope((left + right) / 2)
        cap = route.speed_limit_mps((left + right) / 2)
        cap2 = min(cap, cruise_speed_cap_mps if cruise_speed_cap_mps is not None else cap)**2
        gravity = vehicle.mass_kg * G * slope
        if vehicle.service_brake_force_n + vehicle.resistance_n(0) + gravity <= 0:
            raise InfeasibleRun("Planner requires positive service-braking deceleration on every grade")
        w_right = min(w_right, cap2)
        if w_right >= cap2 - 1e-9:
            bands.append(BrakingBand(left, right, lambda _x, w=cap2: w, False, slope))
            w_right = cap2
            continue

        def rhs(_x, state):
            return [-2 * (vehicle.service_brake_force_n + vehicle.resistance_n(sqrt(max(state[0], 0)))
                          + gravity) / vehicle.effective_mass_kg]

        def reaches_cap(_x, state):
            return state[0] - cap2

        reaches_cap.terminal = True
        reaches_cap.direction = 1
        solution = _spatial_solve(rhs, right, left, w_right, settings, reaches_cap)
        at = float(solution.t[-1])
        bands.append(BrakingBand(at, right, lambda x, sol=solution.sol: float(sol(x)[0]), True, slope))
        if solution.t_events[0].size:
            if at > left:
                bands.append(BrakingBand(left, at, lambda _x, w=cap2: w, False, slope))
            w_right = cap2
        else:
            w_right = float(solution.y[0, -1])
    return sorted(bands, key=lambda b: b.start_m)


def validate_speed_cap(cruise_speed_cap_mps, initial_speed_mps):
    """An optional positive command ceiling; reject an initially overspeed state."""
    finite("initial_speed_mps", initial_speed_mps, 0)
    if cruise_speed_cap_mps is not None:
        finite("cruise_speed_cap_mps", cruise_speed_cap_mps, 0)
        if cruise_speed_cap_mps == 0:
            raise ValueError("cruise_speed_cap_mps must be positive")
        if initial_speed_mps > cruise_speed_cap_mps:
            raise InfeasibleRun("Initial speed exceeds the commanded cruise ceiling")


def plan_journey(vehicle: Vehicle, route: Route, *, initial_speed_mps: float = 0.0,
                 coast_from_m: float | None = None, cruise_speed_cap_mps: float | None = None,
                 settings: Settings = Settings()) -> list[Phase]:
    validate_speed_cap(cruise_speed_cap_mps, initial_speed_mps)
    if coast_from_m is not None:
        finite("coast_from_m", coast_from_m, 0)
        if coast_from_m >= route.length_m:
            raise ValueError("Coasting switch must lie within the route")
    bands = braking_bands(vehicle, route, settings, () if coast_from_m is None else (coast_from_m,),
                          cruise_speed_cap_mps)
    w = initial_speed_mps**2
    if w > bands[0].squared_speed(0) + 1e-7:
        raise InfeasibleRun("Initial speed exceeds the braking envelope or local speed limit")
    phases = []
    for band in bands:
        left, right = band.start_m, band.end_m
        if right - left < 1e-9:
            continue
        coast = coast_from_m is not None and left >= coast_from_m - 1e-8
        command = Command("coast" if coast else "traction")
        ceiling = band.squared_speed(left)
        on_limit = abs(w - ceiling) < 1e-7
        follow = on_limit and band.braking
        if on_limit and not band.braking:
            free = forces(vehicle, sqrt(max(w, 0)), band.dh_ds, command)
            follow = free.acceleration_mps2 >= 0
        if not follow:
            if w <= 1e-10 and forces(vehicle, 0.0, band.dh_ds, command).acceleration_mps2 <= 0:
                raise InfeasibleRun("No forward departure under requested command")

            def rhs(_x, state):
                speed = sqrt(max(state[0], 0))
                return [2 * forces(vehicle, speed, band.dh_ds, command).acceleration_mps2]

            def hits_envelope(x, state):
                return state[0] - band.squared_speed(x)

            hits_envelope.terminal = True
            hits_envelope.direction = 1

            def stops(_x, state):
                return state[0]

            stops.terminal = True
            stops.direction = -1
            solution = _spatial_solve(rhs, left, right, w, settings, [hits_envelope, stops])
            at = float(solution.t[-1])
            w = float(solution.y[0, -1])
            if solution.t_events[1].size:
                raise InfeasibleRun("Train stops before the destination under requested control")
            if at > left + 1e-9:
                phases.append(Phase(left, at, command, band.dh_ds))
            if not solution.t_events[0].size:
                continue
            left = at
        if right - left > 1e-9:
            phases.append(Phase(left, right, Command("brake" if band.braking else "cruise"), band.dh_ds))
        w = band.squared_speed(right)
    if not phases or phases[-1].command.mode != "brake":
        raise InfeasibleRun("No terminal service-braking phase was found")
    return phases


@dataclass
class JourneyResult:
    segments: list[SegmentResult]
    phases: list[Phase]
    time_s: np.ndarray
    states: np.ndarray
    modes: list[str]
    slopes: np.ndarray
    heights_m: np.ndarray
    energy_residual_j: np.ndarray
    electrical: ElectricalEnergy | None = None


def simulate_journey(vehicle: Vehicle, route: Route, *, initial_speed_mps: float = 0.0,
                     coast_from_m: float | None = None, maximum_time_s: float = 3600.0,
                     cruise_speed_cap_mps: float | None = None,
                     settings: Settings = Settings(),
                     electrical: ElectricalParameters | None = None) -> JourneyResult:
    """Replay a plan in time, preserving terminal position/speed errors for checking."""
    finite("maximum_time_s", maximum_time_s, 0)
    if maximum_time_s == 0:
        raise ValueError("maximum_time_s must be positive")
    phases = plan_journey(vehicle, route, initial_speed_mps=initial_speed_mps,
                          coast_from_m=coast_from_m, cruise_speed_cap_mps=cruise_speed_cap_mps,
                          settings=settings)
    state = np.array([0, initial_speed_mps, 0, 0, 0], dtype=float)
    time = 0.0
    segments, times, states, modes, slopes = [], [], [], [], []
    electrical_samples = []
    electrical_offset = np.zeros(3)
    for index, phase in enumerate(phases):
        if time >= maximum_time_s:
            raise InfeasibleRun("Maximum journey time exceeded")
        last = index == len(phases) - 1
        segment = integrate_segment(
            vehicle, phase.command, initial_speed_mps=max(float(state[1]), 0),
            duration_s=maximum_time_s - time, dh_ds=phase.dh_ds,
            initial_position_m=float(state[0]), initial_time_s=time,
            initial_work_j=tuple(state[2:]), end_position_m=None if last else phase.end_m,
            settings=settings, electrical=electrical)
        if segment.termination != ("stopped" if last else "position"):
            raise InfeasibleRun(f"Unexpected replay termination: {segment.termination}")
        # Keep a single sample at a switch, with the new phase's one-sided force.
        if times:
            times.pop()
            states.pop()
            modes.pop()
            slopes.pop()
            if electrical is not None:
                electrical_samples.pop()
        times.extend(segment.time_s)
        states.extend(segment.states.T)
        modes.extend([phase.command.mode] * len(segment.time_s))
        slopes.extend([phase.dh_ds] * len(segment.time_s))
        if electrical is not None:
            cumulative = segment.electrical_integrals_j + electrical_offset[:, None]
            electrical_samples.extend(cumulative.T)
            electrical_offset = cumulative[:, -1]
        segments.append(segment)
        time, state = float(segment.time_s[-1]), segment.states[:, -1]
    array = np.asarray(states).T
    heights = np.array([route.height_m(float(x)) for x in array[0]])
    residual = energy_residual_j(vehicle, array, heights, initial_speed_mps, route.height_m(0))
    result = JourneyResult(segments, phases, np.asarray(times), array, modes, np.asarray(slopes), heights, residual)
    if electrical is not None:
        result.electrical = electrical_energy(electrical, result.time_s, array[2], array[3],
                                              np.asarray(electrical_samples).T)
    speed_excess = max(float(v) - route.speed_limit_mps(float(x)) for x, v in zip(array[0], array[1]))
    energy_scale = max(float(np.max(np.abs(array[2:]))),
                       0.5 * vehicle.effective_mass_kg * float(np.max(np.abs(array[1]**2 - initial_speed_mps**2))),
                       vehicle.mass_kg * G * float(np.max(np.abs(heights - heights[0]))), 1000)
    if abs(array[0, -1] - route.length_m) > 0.5 or abs(array[1, -1]) > 0.05:
        raise InfeasibleRun("Terminal position or speed misses acceptance tolerance")
    if speed_excess > 0.05:
        raise InfeasibleRun("Replay exceeds a route speed restriction")
    if cruise_speed_cap_mps is not None and float(array[1].max()) > cruise_speed_cap_mps + 0.05:
        raise InfeasibleRun("Replay exceeds the commanded cruise ceiling")
    if float(np.max(np.abs(residual))) > 0.001 * energy_scale:
        raise RuntimeError("Mechanical energy balance exceeds acceptance tolerance")
    if abs(vehicle.mass_kg * G * route.slope(route.length_m)) > vehicle.service_brake_force_n:
        raise InfeasibleRun("Insufficient brake force to hold at destination")
    return result
