"""Single-train terminal energy accounting; no storage or network simulation.

Rejected regenerative capability is replaced by friction braking. Only actual
generation incurs conversion loss. All parameters are explicit scenario inputs.
"""

from dataclasses import dataclass

import numpy as np

from .physics import finite


@dataclass(frozen=True)
class ElectricalParameters:
    motoring_efficiency: float
    regenerative_efficiency: float
    auxiliary_power_w: float
    regenerative_force_n: float
    regenerative_wheel_power_w: float
    regenerative_acceptance_fraction: float
    maximum_export_power_w: float

    def __post_init__(self):
        for name, value in vars(self).items():
            finite(name, value, 0)
        for name in ("motoring_efficiency", "regenerative_efficiency", "regenerative_acceptance_fraction"):
            if getattr(self, name) > 1:
                raise ValueError(f"{name} must be <= 1")
        if self.motoring_efficiency == 0:
            raise ValueError("motoring_efficiency must be positive")


@dataclass(frozen=True)
class RegenerativePowers:
    potential_generation_w: float
    wheel_power_w: float
    auxiliary_reuse_w: float


def regenerative_powers(parameters: ElectricalParameters, brake_force_n: float,
                        speed_mps: float) -> RegenerativePowers:
    """Return potential DC generation, actual wheel recovery and auxiliary reuse.

    Acceptance applies to potential generation before allocating auxiliary reuse
    and export. Zero acceptance disables both; rejected demand goes to friction.
    """
    finite("brake_force_n", brake_force_n, 0)
    finite("speed_mps", speed_mps, 0)
    potential = parameters.regenerative_efficiency * min(
        brake_force_n * speed_mps, parameters.regenerative_force_n * speed_mps,
        parameters.regenerative_wheel_power_w)
    accepted = min(parameters.regenerative_acceptance_fraction * potential,
                   parameters.auxiliary_power_w + parameters.maximum_export_power_w)
    wheel = accepted / parameters.regenerative_efficiency if parameters.regenerative_efficiency else 0.0
    return RegenerativePowers(potential, wheel, min(accepted, parameters.auxiliary_power_w))


@dataclass
class ElectricalEnergy:
    motoring_energy_j: np.ndarray
    motoring_loss_j: np.ndarray
    regenerative_potential_energy_j: np.ndarray
    regenerative_wheel_work_j: np.ndarray
    regenerative_generated_energy_j: np.ndarray
    regenerative_accepted_energy_j: np.ndarray
    regenerative_loss_j: np.ndarray
    friction_brake_work_j: np.ndarray
    auxiliary_energy_j: np.ndarray
    auxiliary_reused_energy_j: np.ndarray
    supply_import_energy_j: np.ndarray
    supply_export_energy_j: np.ndarray
    net_supply_energy_j: np.ndarray
    electrical_balance_residual_j: np.ndarray


def electrical_energy(parameters: ElectricalParameters, elapsed_s: np.ndarray,
                      traction_work_j: np.ndarray, brake_work_j: np.ndarray,
                      regenerative_integrals_j: np.ndarray) -> ElectricalEnergy:
    """Build cumulative terminal accounts from ODE-integrated recovery flows.

    Integral rows are potential generation, actual wheel recovery, auxiliary reuse.
    Mechanical work and elapsed time must share the same zero origin.
    """
    potential, wheel, reuse = regenerative_integrals_j
    motoring = traction_work_j / parameters.motoring_efficiency
    generated = parameters.regenerative_efficiency * wheel
    auxiliary = parameters.auxiliary_power_w * elapsed_s
    imported = motoring + auxiliary - reuse
    exported = generated - reuse
    net = imported - exported
    residual = net - (motoring + auxiliary - generated)
    result = ElectricalEnergy(motoring, motoring - traction_work_j, potential, wheel,
                              generated, generated.copy(), wheel - generated,
                              brake_work_j - wheel, auxiliary, reuse, imported,
                              exported, net, residual)
    # Retain raw roundoff, but reject material nonphysical accounts using the
    # same 0.1% energy criterion and 1 kJ scale floor as mechanical acceptance.
    scale = max(float(np.max(np.abs(motoring))), float(np.max(np.abs(brake_work_j))),
                float(np.max(np.abs(auxiliary))), 1000.0)
    tolerance = 0.001 * scale
    for name, values in vars(result).items():
        if not np.isfinite(values).all():
            raise RuntimeError(f"Nonfinite electrical account: {name}")
        if name not in {"net_supply_energy_j", "electrical_balance_residual_j"} and np.min(values) < -tolerance:
            raise RuntimeError(f"Negative electrical account outside tolerance: {name}")
    if (np.any(generated > parameters.regenerative_acceptance_fraction * potential + tolerance)
            or np.any(reuse > generated + tolerance)
            or np.any(reuse > auxiliary + tolerance)
            or np.any(exported > parameters.maximum_export_power_w * elapsed_s + tolerance)
            or np.max(np.abs(residual)) > tolerance):
        raise RuntimeError("Electrical recovery or balance exceeds acceptance tolerance")
    return result
