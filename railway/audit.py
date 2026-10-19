"""Independent sample and phase audits shared by strategy experiments."""

import numpy as np

from .physics import G, forces


def audit_profile(train, route, settings, result, electrical, cruise_speed_cap_mps=None):
    """Check replay samples independently of planning and aggregate summary.

    Uses original segment commands, retaining one-sided force samples at every
    switch. This audits accepted solver samples, not a continuous-time proof.
    """
    t, y = result.time_s, result.states
    x, v, wt, wb, wr = y
    kinetic = 0.5 * train.effective_mass_kg * (v**2 - v[0]**2)
    potential = train.mass_kg * G * (result.heights_m - result.heights_m[0])
    mechanical_residual = wt - wb - wr - kinetic - potential
    energy_scale = max(float(np.max(np.abs(y[2:]))), float(np.max(np.abs(kinetic))),
                       float(np.max(np.abs(potential))), 1000.0)
    traction_excess = brake_excess = power_excess = simultaneous = 0.0
    for segment in result.segments:
        for speed in segment.states[1]:
            speed = max(float(speed), 0.0)
            f = forces(train, speed, segment.dh_ds, segment.command)
            traction_excess = max(traction_excess, f.traction_n - train.available_traction_n(speed))
            brake_excess = max(brake_excess, f.brake_n - train.service_brake_force_n)
            power_excess = max(power_excess, f.traction_n * speed - train.wheel_power_w)
            simultaneous = max(simultaneous, f.traction_n * f.brake_n)
    e = result.electrical
    system_residual = e.net_supply_energy_j - (
        kinetic + potential + wr + e.friction_brake_work_j + e.motoring_loss_j +
        e.regenerative_loss_j + e.auxiliary_energy_j)
    electrical_scale = max(energy_scale, float(np.max(np.abs(e.supply_import_energy_j))))
    metrics = {
        "stop_error_m": float(x[-1] - route.length_m),
        "final_speed_mps": float(v[-1]),
        "minimum_speed_mps": float(v.min()),
        "maximum_speed_excess_mps": max(float(speed) - route.speed_limit_mps(float(position))
                                        for position, speed in zip(x, v)),
        "maximum_traction_force_excess_n": traction_excess,
        "maximum_brake_force_excess_n": brake_excess,
        "maximum_traction_power_excess_w": power_excess,
        "maximum_simultaneous_force_product_n2": simultaneous,
        "maximum_mechanical_balance_residual_j": float(np.max(np.abs(mechanical_residual))),
        "mechanical_balance_tolerance_j": 0.001 * energy_scale,
        "maximum_system_balance_residual_j": float(np.max(np.abs(system_residual))),
        "system_balance_tolerance_j": 0.001 * electrical_scale,
    }
    checks = {
        "commanded_speed_ceiling": cruise_speed_cap_mps is None or float(v.max()) <= cruise_speed_cap_mps + 0.05,
        "finite_states_and_time": bool(np.isfinite(y).all() and np.isfinite(t).all()),
        "increasing_time": bool(np.all(np.diff(t) > 0)),
        "forward_position": bool(np.all(np.diff(x) >= -settings.position_atol_m)),
        "nonnegative_speed": bool(v.min() >= -10 * settings.speed_atol_mps),
        "station_stop": bool(abs(metrics["stop_error_m"]) <= 0.5 and abs(v[-1]) <= 0.05),
        "speed_limits": metrics["maximum_speed_excess_mps"] <= 0.05,
        "traction_force": traction_excess <= 1.0,
        "brake_force": brake_excess <= 1.0,
        "traction_power": power_excess <= 0.001 * train.wheel_power_w,
        "exclusive_traction_braking": simultaneous == 0,
        "nondecreasing_mechanical_work": bool(np.all(np.diff(y[2:], axis=1) >= -settings.work_atol_j)),
        "mechanical_energy_balance": metrics["maximum_mechanical_balance_residual_j"] <= 0.001 * energy_scale,
        "system_energy_balance": metrics["maximum_system_balance_residual_j"] <= 0.001 * electrical_scale,
        "finite_electrical_accounts": all(np.isfinite(values).all() for values in vars(e).values()),
        "recovery_within_brake_work": bool(np.all(e.regenerative_wheel_work_j <= wb + settings.work_atol_j)),
        "accepted_within_potential": bool(np.all(e.regenerative_accepted_energy_j <=
            electrical.regenerative_acceptance_fraction * e.regenerative_potential_energy_j + settings.work_atol_j)),
        "auxiliary_reuse": bool(np.all(e.auxiliary_reused_energy_j <= e.auxiliary_energy_j + settings.work_atol_j)),
        "export_limit": bool(np.all(e.supply_export_energy_j <= electrical.maximum_export_power_w * t + settings.work_atol_j)),
        "nonnegative_losses_and_flows": all(float(getattr(e, name).min()) >= -settings.work_atol_j for name in (
            "motoring_loss_j", "regenerative_loss_j", "friction_brake_work_j", "supply_import_energy_j",
            "supply_export_energy_j", "auxiliary_reused_energy_j")),
    }
    return {"passed": all(checks.values()), "checks": checks, "metrics": metrics}
