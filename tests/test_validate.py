"""
src/kzpy/tests/test_validate.py

validate.py モジュールの以下の関数を pytest で検証するテストモジュールです:
- get_axis_conf: DeviceConfig から軸設定を取得する
- validate_position_pulse, validate_velocity_pulse: パルス範囲チェック
- length_unit_to_pulse / pulse_to_length_unit: 長さ⇔パルス変換
- velocity_unit_to_pulse / pulse_to_velocity_unit: 速度⇔パルス変換
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

# --- テスト用ヘルパー関数 ---

def sample_axis(
    ax_num=1,
    min_pulse=0,
    max_pulse=100,
    max_speed_pulse=50,
    pulse_per_unit=1.0,
) -> AxisConfig:
    """
    AxisConfig のサンプルインスタンスを生成するヘルパー。
    デフォルトで ax_num=1、min_pulse=0、max_pulse=100、max_speed_pulse=50、pulse_per_unit=1.0 に設定。
    """
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


def sample_device_config(axes) -> DeviceConfig:
    """
    DeviceConfig のサンプルインスタンスを生成するヘルパー。
    axes_sum は渡した axes の長さで設定。
    """
    return DeviceConfig(
        device="TestDevice",
        axes_sum=len(axes),
        axes=axes,
        serial={"baudrate": 9600, "parity": "N"},
    )

# --- get_axis_conf のテスト ---

def test_get_axis_conf_returns_correct_axis():
    # 複数軸設定から指定番号の AxisConfig が返ることを確認
    axis1 = sample_axis(ax_num=1)
    axis2 = sample_axis(ax_num=2)
    cfg = sample_device_config([axis1, axis2])

    result = get_axis_conf(cfg, 2)
    assert result is axis2


def test_get_axis_conf_raises_for_missing():
    # 定義外の軸番号を要求すると ValueError が発生
    axis1 = sample_axis(ax_num=1)
    cfg = sample_device_config([axis1])

    with pytest.raises(ValueError) as excinfo:
        get_axis_conf(cfg, 99)
    assert "Axis 99 not defined in config." in str(excinfo.value)

# --- validate_position_pulse のテスト ---

def test_validate_position_pulse_within_bounds_returns_pulse():
    # 範囲内の値はそのまま返されることを確認
    axis = sample_axis(min_pulse=-10, max_pulse=10)
    assert validate_position_pulse(0, axis) == 0
    assert validate_position_pulse(10, axis) == 10
    assert validate_position_pulse(-10, axis) == -10


def test_validate_position_pulse_below_min_raises():
    # min_pulse より小さい値でエラー
    axis = sample_axis(min_pulse=0, max_pulse=100)
    with pytest.raises(ValueError) as excinfo:
        validate_position_pulse(-1, axis)
    assert "Position pulse -1 out of range [0, 100]." in str(excinfo.value)


def test_validate_position_pulse_above_max_raises():
    # max_pulse より大きい値でエラー
    axis = sample_axis(min_pulse=0, max_pulse=50)
    with pytest.raises(ValueError) as excinfo:
        validate_position_pulse(51, axis)
    assert "Position pulse 51 out of range [0, 50]." in str(excinfo.value)

# --- validate_velocity_pulse のテスト ---

def test_validate_velocity_pulse_within_bounds_returns_pulse():
    # 範囲内の速度パルスはそのまま返される
    axis = sample_axis(max_speed_pulse=20)
    assert validate_velocity_pulse(0, axis) == 0
    assert validate_velocity_pulse(20, axis) == 20


def test_validate_velocity_pulse_negative_raises():
    # 負の値でエラー
    axis = sample_axis(max_speed_pulse=10)
    with pytest.raises(ValueError) as excinfo:
        validate_velocity_pulse(-1, axis)
    assert "Velocity pulse -1 exceeds max_speed_pulse 10." in str(excinfo.value)


def test_validate_velocity_pulse_above_max_raises():
    # max_speed_pulse を超える値でエラー
    axis = sample_axis(max_speed_pulse=5)
    with pytest.raises(ValueError) as excinfo:
        validate_velocity_pulse(6, axis)
    assert "Velocity pulse 6 exceeds max_speed_pulse 5." in str(excinfo.value)

# --- 長さ ⇔ パルス 変換のテスト ---

def test_length_unit_to_pulse_and_back():
    # length_unit_to_pulse / pulse_to_length_unit の双方向変換確認
    axis = sample_axis(pulse_per_unit=2.5, min_pulse=0, max_pulse=100)
    length = 5.0
    pulses = length_unit_to_pulse(length, axis)
    # int(5.0 / 2.5) = 2
    assert pulses == 2
    result_length = pulse_to_length_unit(pulses, axis)
    assert pytest.approx(result_length) == length


def test_length_unit_to_pulse_out_of_range_raises():
    # 長さから計算したパルスが範囲外の場合エラー
    axis = sample_axis(pulse_per_unit=10, min_pulse=0, max_pulse=10)
    with pytest.raises(ValueError):
        length_unit_to_pulse(200.0, axis)


def test_pulse_to_length_unit_out_of_range_raises():
    # パルス値が範囲外の場合エラー
    axis = sample_axis(min_pulse=0, max_pulse=5, pulse_per_unit=1.0)
    with pytest.raises(ValueError):
        pulse_to_length_unit(10, axis)

# --- 速度 ⇔ パルス 変換のテスト ---

def test_velocity_unit_to_pulse_and_back():
    # velocity_unit_to_pulse / pulse_to_velocity_unit の双方向変換確認
    axis = sample_axis(pulse_per_unit=4.0, max_speed_pulse=100)
    velocity = 8.0
    pulses = velocity_unit_to_pulse(velocity, axis)
    # int(8.0 / 4.0) = 2
    assert pulses == 2
    result_velocity = pulse_to_velocity_unit(pulses, axis)
    assert pytest.approx(result_velocity) == velocity


def test_velocity_unit_to_pulse_out_of_range_raises():
    # 計算した速度パルスが範囲外の場合エラー
    axis = sample_axis(pulse_per_unit=10.0, max_speed_pulse=20)
    with pytest.raises(ValueError):
        velocity_unit_to_pulse(500.0, axis)


def test_pulse_to_velocity_unit_out_of_range_raises():
    # パルス値が範囲外の場合エラー
    axis = sample_axis(max_speed_pulse=5)
    with pytest.raises(ValueError):
        pulse_to_velocity_unit(10, axis)
    with pytest.raises(ValueError):
        pulse_to_velocity_unit(-1, axis)
