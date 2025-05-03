"""
src/kzpy/validate.py

デバイス設定値や物理単位変換に関するバリデーション／ユーティリティ関数を提供するモジュール:
- グローバルな許容範囲定義
- 設定ファイルからの軸設定取得
- パルス数・物理単位間の変換とチェック
- WTBコマンド用のacc_time, dec_time, acc_typeのバリデーション
"""
from typing import Any
from ._type import DeviceConfig, AxisConfig

# --- グローバル定義: 外部から設定可能なバリデーションパラメータ ---
# 加速／減速時間の最小・最大値（パルスカウント単位）
ACC_TIME_RANGE = (1, 10_000)     # (min_acc_time, max_acc_time)
DEC_TIME_RANGE = (1, 10_000)     # (min_dec_time, max_dec_time)
# variantごとに許容されるacc_typeのオプション
ACC_TYPE_OPTIONS = {
    'default': (1, 2),
    'aries':   (1, 2, 3),
}

# --- 設定取得関数 ---
def get_axis_conf(config: DeviceConfig, ax_num: int) -> AxisConfig:
    """
    DeviceConfig.axes リストから、指定された軸番号(ax_num)の設定を取得する。
    定義が見つからなければValueErrorを送出。
    """
    for ax in config.axes:
        if ax.ax_num == ax_num:
            return ax
    raise ValueError(f"Axis {ax_num} not defined in config.")

# --- パルス数の範囲チェック ---
def validate_position_pulse(pulse: int, axis: AxisConfig) -> int:
    """
    位置制御用パルス数が axis.min_pulse～axis.max_pulse の範囲内か検証し、問題なければ値を返す。
    範囲外の場合はValueErrorを送出。
    """
    if pulse < axis.min_pulse or pulse > axis.max_pulse:
        raise ValueError(
            f"Position pulse {pulse} out of range [{axis.min_pulse}, {axis.max_pulse}]."
        )
    return pulse


def validate_velocity_pulse(pulse: int, axis: AxisConfig) -> int:
    """
    速度制御用パルス数が0～axis.max_speed_pulseの範囲内か検証し、問題なければ値を返す。
    範囲外の場合はValueErrorを送出。
    """
    if pulse < 0 or pulse > axis.max_speed_pulse:
        raise ValueError(
            f"Velocity pulse {pulse} exceeds max_speed_pulse {axis.max_speed_pulse}."
        )
    return pulse

# --- 単位変換関数 ---
# axis.pulse_per_unit: 1パルスあたりの物理単位変位を表す (unit/pulse)

def length_unit_to_pulse(length: float, axis: AxisConfig) -> int:
    """
    物理長さ(length)をaxis.pulse_per_unitで割ってパルス数に変換し、範囲チェックを行う。
    """
    pulses = int(length / axis.pulse_per_unit)
    return validate_position_pulse(pulses, axis)


def pulse_to_length_unit(pulse: int, axis: AxisConfig) -> float:
    """
    パルス数から物理長さに変換し、範囲チェックを行う。
    """
    validate_position_pulse(pulse, axis)
    return pulse * axis.pulse_per_unit


def velocity_unit_to_pulse(velocity: float, axis: AxisConfig) -> int:
    """
    物理速度(velocity)をaxis.pulse_per_unitで割ってパルス/秒に変換し、範囲チェックを行う。
    """
    pulses = int(velocity / axis.pulse_per_unit)
    return validate_velocity_pulse(pulses, axis)


def pulse_to_velocity_unit(pulse: int, axis: AxisConfig) -> float:
    """
    パルス/秒から物理速度に変換し、範囲チェックを行う。
    """
    validate_velocity_pulse(pulse, axis)
    return pulse * axis.pulse_per_unit

# --- WTBコマンド用バリデーション関数 ---
def validate_acc_time(acc_time: int, axis: AxisConfig) -> int:
    """
    acc_time がグローバル範囲(ACC_TIME_RANGE)内か検証し、問題なければ値を返す。
    範囲外の場合はValueErrorを送出。
    """
    min_val, max_val = ACC_TIME_RANGE
    if acc_time < min_val or acc_time > max_val:
        raise ValueError(f"acc_time {acc_time} out of global range [{min_val}, {max_val}].")
    return acc_time


def validate_dec_time(dec_time: int, axis: AxisConfig) -> int:
    """
    dec_time がグローバル範囲(DEC_TIME_RANGE)内か検証し、問題なければ値を返す。
    範囲外の場合はValueErrorを送出。
    """
    min_val, max_val = DEC_TIME_RANGE
    if dec_time < min_val or dec_time > max_val:
        raise ValueError(f"dec_time {dec_time} out of global range [{min_val}, {max_val}].")
    return dec_time


def validate_acc_type(acc_type: int, variant: str) -> int:
    """
    variant(default/aries)に応じて、acc_typeが許容オプション(ACC_TYPE_OPTIONS)のいずれかであるかを確認し、
    問題なければ値を返す。範囲外の場合はValueErrorを送出。
    """
    valid = ACC_TYPE_OPTIONS.get(variant, ACC_TYPE_OPTIONS['default'])
    if acc_type not in valid:
        raise ValueError(
            f"acc_type {acc_type} invalid for variant '{variant}'; must be one of {valid}"
        )
    return acc_type
