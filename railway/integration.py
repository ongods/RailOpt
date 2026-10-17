"""Event-aware time integration of motion and mechanical work on one slope."""

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from .physics import Command, G, InfeasibleRun, Vehicle, finite, forces


@dataclass(frozen=True)
class Settings:
    max_step_s: float = 0.25
    rtol: float = 1e-9
    position_atol_m: float = 1e-8
    speed_atol_mps: float = 1e-9
    work_atol_j: float = 1e-3
    planning_step_m: float = 5.0

    def __post_init__(self):
        for name, value in vars(self).items():
            finite(name, value, 0)
            if value == 0:
                raise ValueError(f"{name} must be positive")


@dataclass
class SegmentResult:
    time_s: np.ndarray
    states: np.ndarray  # rows: x [m], v [m/s], W_T [J], W_B [J], W_R [J]
    termination: str
    command: Command
    dh_ds: float


def integrate_segment(
    vehicle: Vehicle,
    command: Command,
    *,
    initial_speed_mps: float,
    duration_s: float,
    dh_ds: float = 0.0,
    initial_position_m: float = 0.0,
    initial_time_s: float = 0.0,
    initial_work_j: tuple[float, float, float] = (0.0, 0.0, 0.0),
    end_position_m: float | None = None,
    settings: Settings = Settings(),
) -> SegmentResult:
    """Terminate at duration, a distance boundary, or the first downward v=0 event.
    Trial RK stages may cross zero; the RHS is extended there for event location.
    Accepted trajectories are never repaired by clipping speed or position.
    """
    finite("initial_speed_mps", initial_speed_mps, 0)
    finite("initial_position_m", initial_position_m)
    finite("initial_time_s", initial_time_s, 0)
    finite("duration_s", duration_s, 0)
    if duration_s == 0:
        raise ValueError("duration_s must be positive")
    if len(initial_work_j) != 3:
        raise ValueError("initial_work_j needs traction, brake and resistance work")
    for work in initial_work_j:
        finite("initial_work_j", work, 0)
    if end_position_m is not None:
        finite("end_position_m", end_position_m)
        if end_position_m <= initial_position_m:
            raise ValueError("end_position_m must exceed initial position")
    first = forces(vehicle, initial_speed_mps, dh_ds, command)
    if initial_speed_mps == 0 and command.mode != "hold" and first.acceleration_mps2 <= 0:
        raise InfeasibleRun("Forward departure is impossible; use explicit hold for a stationary train")

    def rhs(_time, state):
        speed = max(float(state[1]), 0.0)  # trial-stage extension only
        force = forces(vehicle, speed, dh_ds, command)
        return [speed, force.acceleration_mps2, force.traction_n * speed,
                force.brake_n * speed, force.resistance_n * speed]

    def stopped(_time, state):
        return state[1]

    stopped.terminal = True
    stopped.direction = -1

    def arrived(_time, state):
        return state[0] - end_position_m

    arrived.terminal = True
    arrived.direction = 1
    events = [] if command.mode == "hold" else [stopped]
    if end_position_m is not None:
        if command.mode == "hold":
            raise ValueError("A holding train cannot reach a distance boundary")
        events.append(arrived)

    # Resolve the force/power kink explicitly before continuing in the next regime.
    transition = None
    if command.mode == "traction" and vehicle.traction_force_n > 0 and vehicle.wheel_power_w > 0:
        transition = vehicle.wheel_power_w / vehicle.traction_force_n

    def power_transition(_time, state):
        return state[1] - transition

    power_transition.terminal = True
    power_transition.direction = 0
    state = np.array([initial_position_m, initial_speed_mps, *initial_work_j], dtype=float)
    time = initial_time_s
    final_time = initial_time_s + duration_s
    times, states = [], []
    termination = "duration"
    # A constant command on a constant slope has at most one power-boundary crossing.
    transition_pending = transition is not None and abs(initial_speed_mps - transition) > 1e-10
    while time < final_time:
        active_events = events + ([power_transition] if transition_pending else [])
        sol = solve_ivp(rhs, (time, final_time), state, method="DOP853", events=active_events,
                        rtol=settings.rtol, atol=[settings.position_atol_m, settings.speed_atol_mps,
                                                 *([settings.work_atol_j] * 3)], max_step=settings.max_step_s)
        if not sol.success or not np.isfinite(sol.y).all():
            raise RuntimeError(f"Time integration failed: {sol.message}")
        start = 1 if times else 0
        times.extend(sol.t[start:])
        states.extend(sol.y.T[start:])
        time, state = float(sol.t[-1]), sol.y[:, -1]
        hit = next((i for i, values in enumerate(sol.t_events) if len(values)), None)
        if transition_pending and hit == len(events):
            transition_pending = False
            continue
        if hit is not None:
            termination = "stopped" if hit == 0 else "position"
        break
    result = SegmentResult(np.asarray(times), np.asarray(states).T, termination, command, dh_ds)
    if result.states[1].min() < -10 * settings.speed_atol_mps:
        raise RuntimeError("Negative speed outside zero-event tolerance")
    return result


def energy_residual_j(vehicle: Vehicle, states: np.ndarray, heights_m: np.ndarray,
                      initial_speed_mps: float = 0.0, initial_height_m: float = 0.0) -> np.ndarray:
    """Work balance relative to the initial state; works are cumulative from run start."""
    kinetic_change = 0.5 * vehicle.effective_mass_kg * (states[1]**2 - initial_speed_mps**2)
    potential_change = vehicle.mass_kg * G * (heights_m - initial_height_m)
    return states[2] - states[3] - states[4] - kinetic_change - potential_change
