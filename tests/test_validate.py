"""
test_validate.py
pytestを用いて src/kzpy/validate.py の各関数（軸の取得、パルス/単位変換、およびバリデーション）を検証します。
"""
import pytest
from src.kzpy.validate import (
    get_axis_conf,
    validate_position_pulse,
    validate_velocity_pulse,
    length_unit_to_pulse,
    pulse_to_length_unit,
    velocity_unit_to_pulse,
    pulse_to_velocity_unit,
)
from src.kzpy._type import AxisConfig, DeviceConfig

# テスト用の AxisConfig インスタンスを生成するヘルパー関数
# デフォルト値: ax_num=1, min_pulse=0, max_pulse=100, max_speed_pulse=50, pulse_per_unit=1.0

def sample_axis(
    ax_num=1,
    min_pulse=0,
    max_pulse=100,
    max_speed_pulse=50,
    pulse_per_unit=1.0,
) -> AxisConfig:
    return AxisConfig(
        name=f"axis{ax_num}",
        ax_num=ax_num,
        units="unit",
        min_pulse=min_pulse,
        max_pulse=max_pulse,
        max_speed_pulse=max_speed_pulse,
        start_velocity_pulse=1.0,
        pulse_per_unit=pulse_per_unit,
    )

# テスト用の DeviceConfig インスタンスを生成するヘルパー関数
# axes のリストを渡すと、その数を axes_sum に設定します

def sample_device_config(axes) -> DeviceConfig:
    return DeviceConfig(
        device="TestDevice",
        axes_sum=len(axes),
        axes=axes,
        serial={"baudrate": 9600, "parity": "N"},
    )

# get_axis_conf のテスト

def test_get_axis_conf_returns_correct_axis():
    """
    ax_num に対応する AxisConfig が正しく返されることを確認します。
    """
    axis1 = sample_axis(ax_num=1)
    axis2 = sample_axis(ax_num=2)
    cfg = sample_device_config([axis1, axis2])

    result = get_axis_conf(cfg, 2)
    # ax_num=2 の軸が返されること
    assert result is axis2


def test_get_axis_conf_raises_for_missing():
    """
    定義されていない ax_num を指定した際に ValueError が発生することを確認します。
    """
    axis1 = sample_axis(ax_num=1)
    cfg = sample_device_config([axis1])

    with pytest.raises(ValueError) as excinfo:
        get_axis_conf(cfg, 99)
    assert "Axis 99 not defined in config." in str(excinfo.value)

# validate_position_pulse のテスト

def test_validate_position_pulse_within_bounds_returns_pulse():
    """
    pulse が min_pulse ～ max_pulse の範囲内の場合、同じ値が返されることを確認します。
    """
    axis = sample_axis(min_pulse=-10, max_pulse=10)
    assert validate_position_pulse(0, axis) == 0
    assert validate_position_pulse(10, axis) == 10
    assert validate_position_pulse(-10, axis) == -10


def test_validate_position_pulse_below_min_raises():
    """
    pulse が min_pulse 未満の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(min_pulse=0, max_pulse=100)
    with pytest.raises(ValueError) as excinfo:
        validate_position_pulse(-1, axis)
    assert "Position pulse -1 out of range [0, 100]." in str(excinfo.value)


def test_validate_position_pulse_above_max_raises():
    """
    pulse が max_pulse 超過の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(min_pulse=0, max_pulse=50)
    with pytest.raises(ValueError) as excinfo:
        validate_position_pulse(51, axis)
    assert "Position pulse 51 out of range [0, 50]." in str(excinfo.value)

# validate_velocity_pulse のテスト

def test_validate_velocity_pulse_within_bounds_returns_pulse():
    """
    pulse が 0 ～ max_speed_pulse の範囲内の場合、同じ値が返されることを確認します。
    """
    axis = sample_axis(max_speed_pulse=20)
    assert validate_velocity_pulse(0, axis) == 0
    assert validate_velocity_pulse(20, axis) == 20


def test_validate_velocity_pulse_negative_raises():
    """
    pulse が負の値の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(max_speed_pulse=10)
    with pytest.raises(ValueError) as excinfo:
        validate_velocity_pulse(-1, axis)
    assert "Velocity pulse -1 exceeds max_speed_pulse 10." in str(excinfo.value)


def test_validate_velocity_pulse_above_max_raises():
    """
    pulse が max_speed_pulse 超過の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(max_speed_pulse=5)
    with pytest.raises(ValueError) as excinfo:
        validate_velocity_pulse(6, axis)
    assert "Velocity pulse 6 exceeds max_speed_pulse 5." in str(excinfo.value)

# 単位 ⇔ パルス 変換のテスト

def test_length_unit_to_pulse_and_back():
    """
    length_unit_to_pulse が長さをパルスに変換し、pulse_to_length_unit が元に戻すことを確認します。
    """
    axis = sample_axis(pulse_per_unit=2.5, min_pulse=0, max_pulse=100)
    length = 4.0
    pulses = length_unit_to_pulse(length, axis)
    # int(4.0 * 2.5) = 10
    assert pulses == 10
    result_length = pulse_to_length_unit(pulses, axis)
    assert pytest.approx(result_length) == length


def test_length_unit_to_pulse_out_of_range_raises():
    """
    変換後のパルスが範囲外の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(pulse_per_unit=10, min_pulse=0, max_pulse=10)
    with pytest.raises(ValueError):
        length_unit_to_pulse(2.0, axis)


def test_pulse_to_length_unit_out_of_range_raises():
    """
    pulse_to_length_unit において入力パルスが範囲外の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(min_pulse=0, max_pulse=5, pulse_per_unit=1.0)
    with pytest.raises(ValueError):
        pulse_to_length_unit(10, axis)

# 速度単位 ⇔ パルス 変換のテスト

def test_velocity_unit_to_pulse_and_back():
    """
    velocity_unit_to_pulse が速度をパルスに変換し、pulse_to_velocity_unit が元に戻すことを確認します。
    """
    axis = sample_axis(pulse_per_unit=4.0, max_speed_pulse=100)
    velocity = 3.5
    pulses = velocity_unit_to_pulse(velocity, axis)
    # int(3.5 * 4.0) = 14
    assert pulses == 14
    result_velocity = pulse_to_velocity_unit(pulses, axis)
    assert pytest.approx(result_velocity) == velocity


def test_velocity_unit_to_pulse_out_of_range_raises():
    """
    変換後の速度パルスが max_speed_pulse を超過する場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(pulse_per_unit=10.0, max_speed_pulse=20)
    with pytest.raises(ValueError):
        velocity_unit_to_pulse(3.0, axis)


def test_pulse_to_velocity_unit_out_of_range_raises():
    """
    pulse_to_velocity_unit において入力パルスが負または max_speed_pulse 超過の場合に ValueError が発生することを確認します。
    """
    axis = sample_axis(max_speed_pulse=5)
    with pytest.raises(ValueError):
        pulse_to_velocity_unit(10, axis)
    with pytest.raises(ValueError):
        pulse_to_velocity_unit(-1, axis)
