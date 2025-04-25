"""
src/kzpy/_type.py

Pydanticを利用して型定義とバリデーションを一元化します:
  - AxisConfig: 各軸の設定情報を保持
  - SerialConfig: シリアル通信設定を保持
  - DeviceConfig: デバイス全体の設定をまとめる
"""
from typing import Annotated, List
from pydantic import BaseModel, Field, field_validator, model_validator

class AxisConfig(BaseModel):
    name: str
    ax_num: Annotated[int, Field(..., ge=0)]
    units: str
    max_pulse: int
    min_pulse: int
    max_speed_pulse: int
    start_velocity_pulse: Annotated[float, Field(..., gt=0)]
    pulse_per_unit: Annotated[float, Field(..., gt=0)]

class SerialConfig(BaseModel):
    baudrate: Annotated[int, Field(..., gt=0)]
    parity: str

    @field_validator('parity')
    def validate_parity(cls, v: str) -> str:
        allowed = {'N', 'E', 'O'}
        if v not in allowed:
            raise ValueError(f"parity must be one of {allowed}, got {v!r}")
        return v

class DeviceConfig(BaseModel):
    device: str
    axes_sum: Annotated[int, Field(..., ge=0)]
    axes: List[AxisConfig]
    serial: SerialConfig

    @model_validator(mode='after')
    def check_axes_length(cls, m: 'DeviceConfig') -> 'DeviceConfig':
        if m.axes_sum != len(m.axes):
            raise ValueError(f"axes_sum ({m.axes_sum}) must equal len(axes) ({len(m.axes)})")
        return m
