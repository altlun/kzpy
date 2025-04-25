# src/kzpy/validate.py

from typing import Any
from ._type import DeviceConfig, AxisConfig

def get_axis_conf(config: DeviceConfig, ax_num: int) -> AxisConfig:
    for ax in config.axes:
        if ax.ax_num == ax_num:
            return ax
    raise ValueError(f"Axis {ax_num} not defined in config.")

def validate_position_pulse(pulse: int, axis: AxisConfig) -> int:
    if pulse < axis.min_pulse or pulse > axis.max_pulse:
        raise ValueError(
            f"Position pulse {pulse} out of range [{axis.min_pulse}, {axis.max_pulse}]."
        )
    return pulse

def validate_velocity_pulse(pulse: int, axis: AxisConfig) -> int:
    if pulse < 0 or pulse > axis.max_speed_pulse:
        raise ValueError(
            f"Velocity pulse {pulse} exceeds max_speed_pulse {axis.max_speed_pulse}."
        )
    return pulse

def length_unit_to_pulse(length: float, axis: AxisConfig) -> int:
    """
    unit → pulse
    """
    pulses = int(length * axis.pulse_per_unit)
    return validate_position_pulse(pulses, axis)

def pulse_to_length_unit(pulse: int, axis: AxisConfig) -> float:
    """
    pulse → unit
    """
    validate_position_pulse(pulse, axis)
    return pulse / axis.pulse_per_unit

def velocity_unit_to_pulse(velocity: float, axis: AxisConfig) -> int:
    """
    unit/s → pulse/s
    """
    pulses = int(velocity * axis.pulse_per_unit)
    return validate_velocity_pulse(pulses, axis)

def pulse_to_velocity_unit(pulse: int, axis: AxisConfig) -> float:
    """
    pulse/s → unit/s
    """
    validate_velocity_pulse(pulse, axis)
    return pulse / axis.pulse_per_unit
