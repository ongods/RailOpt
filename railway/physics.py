"""SI force balance for a forward-moving point train.
Gravity uses actual mass; acceleration and kinetic energy use effective mass.
The constant service-brake force is an explicit approximation, not an OEM map.
"""

from dataclasses import dataclass
from math import isfinite, sqrt

G = 9.80665


def finite(name: str, value: float, minimum: float | None = None) -> None:
    if not isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{name} must be finite" + (f" and >= {minimum}" if minimum is not None else ""))


@dataclass(frozen=True)
class Vehicle:
    mass_kg: float
    rotating_mass_kg: float
    traction_force_n: float
    wheel_power_w: float
    service_brake_force_n: float
    davis_a_n: float
    davis_b_ns_per_m: float
    davis_c_ns2_per_m2: float

    def __post_init__(self):
        for name, value in vars(self).items():
            finite(name, value, 0)
        if self.mass_kg == 0:
            raise ValueError("mass_kg must be positive")

    @property
    def effective_mass_kg(self) -> float:
        return self.mass_kg + self.rotating_mass_kg

    def resistance_n(self, speed_mps: float) -> float:
        finite("speed_mps", speed_mps, 0)
        return self.davis_a_n + self.davis_b_ns_per_m * speed_mps + self.davis_c_ns2_per_m2 * speed_mps**2

    def available_traction_n(self, speed_mps: float) -> float:
        finite("speed_mps", speed_mps, 0)
        if self.wheel_power_w == 0:
            return 0.0
        return self.traction_force_n if speed_mps == 0 else min(self.traction_force_n, self.wheel_power_w / speed_mps)


def slope_from_grade(grade_fraction: float) -> float:
    """Convert rise/horizontal-run grade to dh/ds for along-track distance s."""
    finite("grade_fraction", grade_fraction)
    return grade_fraction / sqrt(1 + grade_fraction**2)


@dataclass(frozen=True)
class Command:
    mode: str
    fraction: float = 1.0

    def __post_init__(self):
        if self.mode not in {"traction", "coast", "brake", "cruise", "hold"}:
            raise ValueError(f"Unknown control mode: {self.mode}")
        finite("fraction", self.fraction, 0)
        if self.fraction > 1:
            raise ValueError("fraction must be <= 1")


class InfeasibleRun(ValueError):
    """The configured capability cannot realize the requested motion."""


@dataclass(frozen=True)
class Forces:
    traction_n: float
    brake_n: float
    resistance_n: float
    grade_n: float
    acceleration_mps2: float


def forces(vehicle: Vehicle, speed_mps: float, dh_ds: float, command: Command) -> Forces:
    finite("dh_ds", dh_ds)
    if abs(dh_ds) >= 1:
        raise ValueError("abs(dh_ds) must be < 1")
    resistance = vehicle.resistance_n(speed_mps)
    gravity = vehicle.mass_kg * G * dh_ds
    traction = brake = 0.0
    if command.mode == "traction":
        traction = command.fraction * vehicle.available_traction_n(speed_mps)
    elif command.mode == "brake":
        brake = command.fraction * vehicle.service_brake_force_n
    elif command.mode == "cruise":
        demand = resistance + gravity
        if demand >= 0:
            if demand > vehicle.available_traction_n(speed_mps) + 1e-8:
                raise InfeasibleRun("Insufficient traction to maintain speed")
            traction = demand
        else:
            if -demand > vehicle.service_brake_force_n + 1e-8:
                raise InfeasibleRun("Insufficient braking to maintain speed")
            brake = -demand
    elif command.mode == "hold":
        if speed_mps != 0:
            raise ValueError("Holding requires zero speed")
        if abs(gravity) > vehicle.service_brake_force_n:
            raise InfeasibleRun("Insufficient brake force to hold on this grade")
        # Static holding reaction is not rolling resistance and does no work.
        return Forces(0.0, abs(gravity), 0.0, gravity, 0.0)
    acceleration = (traction - brake - resistance - gravity) / vehicle.effective_mass_kg
    return Forces(traction, brake, resistance, gravity, acceleration)
