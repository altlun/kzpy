
"""
tests/test_type.py
pytest を使って、Pydantic v2 モデルのバリデーションを検証します。
"""
import pytest
from pydantic import ValidationError
from src.kzpy._type import AxisConfig, SerialConfig, DeviceConfig

# サンプルデータ生成関数
def sample_axis():
    return {
        "name": "z1",
        "ax_num": 1,
        "units": "um",
        "max_pulse": 20000,
        "min_pulse": -20000,
        "max_speed_pulse": 20000,
        "start_velocity_pulse": 0.5,
        "pulse_per_unit": 0.125,
    }

valid_serial = {"baudrate": 115200, "parity": "N"}

# --- 正常系テスト ---
def test_axis_config_creation():
    axis = AxisConfig(**sample_axis())
    assert axis.ax_num == 1
    assert axis.pulse_per_unit > 0

@pytest.mark.parametrize("baud,parity", [
    (115200, 'N'),
    (9600, 'E'),
])
def test_serial_config_valid(baud, parity):
    serial = SerialConfig(baudrate=baud, parity=parity)
    assert serial.baudrate == baud
    assert serial.parity == parity


def test_device_config_creation_valid():
    axes = [AxisConfig(**sample_axis()) for _ in range(3)]
    device = DeviceConfig(
        device="Aries",
        axes_sum=3,
        axes=axes,
        serial=SerialConfig(**valid_serial)
    )
    assert device.axes_sum == len(device.axes)

# --- 異常系テスト ---
@pytest.mark.parametrize("data", [
    {"baudrate": 0, "parity": "N"},        # baudrate <= 0
    {"baudrate": 115200, "parity": "X"},   # parity 不正
])
def test_serial_config_invalid(data):
    with pytest.raises(ValidationError):
        SerialConfig(**data)

@pytest.mark.parametrize("count", [0, -1])
def test_axis_config_invalid_start_velocity(count):
    data = sample_axis()
    data['start_velocity_pulse'] = count
    with pytest.raises(ValidationError):
        AxisConfig(**data)


def test_device_config_axes_mismatch():
    axes = [AxisConfig(**sample_axis())] * 2
    with pytest.raises(ValidationError):
        DeviceConfig(
            device="A",
            axes_sum=3,
            axes=axes,
            serial=SerialConfig(**valid_serial)
        )
