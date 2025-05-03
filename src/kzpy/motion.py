"""
src/kzpy/device.py

config/*.json から設定を読み込み、DeviceConfig モデルを元にシリアルデバイスとの通信を管理します。
- デバイスの自動検出や接続確認、コマンド送信・受信処理を提供
"""

from typing import Dict, Any, Optional

from .validate import (
    get_axis_conf,
    length_unit_to_pulse,
    pulse_to_length_unit,
    velocity_unit_to_pulse,
    pulse_to_velocity_unit,
    validate_acc_time,
    validate_dec_time,
    validate_acc_type,
)
from .device import Device


class MotionController:
    def __init__(self, device: Device):
        """デバイスインスタンスを受け取り、構成情報を保持"""
        self._dev = device
        self._cfg = device._config

    def _exec_int(self, name: str, **kwargs) -> Dict[str, Any]:
        """キーワード引数を整数に変換し、コマンドを実行"""
        return self._dev._execute_command(name, **{k: int(v) for k, v in kwargs.items()})

    def _get_processor(self):
        """コマンドプロセッサを取得（variantなどにアクセスする用途）"""
        return getattr(self._dev, '_cmd', None) or getattr(self._dev, '_processor', None)

    def _convert_velocity_to_pulses(self, velocity: float, ax_conf: dict) -> int:
        """速度（単位系）をパルス数に変換"""
        return velocity_unit_to_pulse(velocity, ax_conf)

    def _convert_pulses_to_velocity(self, pulses: int, ax_conf: dict) -> float:
        """パルス数を速度（単位系）に変換"""
        return pulse_to_velocity_unit(pulses, ax_conf)

    def _get_vel_table_scaling(self, orig: dict, max_pulse: int) -> float:
        """元の速度テーブルと新しい最大速度の比率を求める"""
        orig_max = int(orig.get('max_vel', max_pulse))
        return max_pulse / orig_max if orig_max else 1.0

    def _temp_set_velocity(self, ax: int, vel_no: int, velocity: float) -> Dict[str, Any]:
        """一時的に速度テーブルを書き換える"""
        axis_cfg = get_axis_conf(self._cfg, ax)
        max_pulse = self._convert_velocity_to_pulses(velocity, axis_cfg)
        start_pulse = int(max_pulse * 0.8)

        proc = self._get_processor()
        orig = self._exec_int('read_vel_tbl', ax_num=ax, vel_no=vel_no)
        orig['_variant'] = getattr(proc, 'variant', None)

        scale = self._get_vel_table_scaling(orig, max_pulse)
        new_acc_time = max(1, int(float(orig.get('acc_time', 1)) * scale))

        write_args = {
            'ax_num':    ax,
            'vel_no':    vel_no,
            'start_vel': start_pulse,
            'max_vel':   max_pulse,
            'acc_time':  new_acc_time,
            'acc_type':  int(orig.get('acc_type', 1)),
        }

        if 'dec_time' in orig:
            orig_dec = float(orig.get('dec_time', orig['acc_time']))
            write_args['dec_time'] = max(1, int(orig_dec * scale))

        self._exec_int('write_vel_tbl', **write_args)
        return orig

    def _restore_vel_tbl(self, orig: Dict[str, Any]) -> None:
        """速度テーブルを元の値に戻す（variantも含む）"""
        proc = self._get_processor()
        if '_variant' in orig and orig['_variant'] is not None:
            proc.variant = orig['_variant']

        args_list = proc.cmd_map['write_vel_tbl']['args']
        restore_args = {arg: int(orig[arg]) for arg in args_list if arg in orig}
        print(f"[DEBUG] Restoring write_vel_tbl with variant={getattr(proc, 'variant', None)}, args={restore_args}")
        self._exec_int('write_vel_tbl', **restore_args)

    def move_relative(self, axis: int, length: float, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        """相対移動を実行する"""
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_len = length_unit_to_pulse(length, ax_conf)
        table_no = vel_no or self._dev.target_vel_no

        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no else None
        resp = self._exec_int('move_relative', ax_num=axis, vel_no=table_no, length=pulse_len, pat=1)

        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)

        return {
            'length': resp.get('length'),
            'length_pulse': pulse_len,
            'velocity': velocity,
            'velocity_pulse': self._convert_velocity_to_pulses(velocity, ax_conf),
            **resp
        }

    def move_absolute(self, axis: int, position: float, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        """絶対移動を実行する"""
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_pos = length_unit_to_pulse(position, ax_conf)
        table_no = vel_no or self._dev.target_vel_no

        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no else None
        resp = self._exec_int('move_absolute', ax_num=axis, vel_no=table_no, length=pulse_pos, pat=1)

        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)

        return {
            'position': resp.get('length'),
            'position_pulse': pulse_pos,
            'velocity': velocity,
            'velocity_pulse': self._convert_velocity_to_pulses(velocity, ax_conf),
            **resp
        }

    def move_stop(self, axis: int, pat: int = 1) -> Dict[str, Any]:
        """現在の動作を停止させる"""
        return self._exec_int('move_stop', ax_num=axis, pat=pat)

    def home(self, axis: int, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        """原点復帰動作を行う"""
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_vel = self._convert_velocity_to_pulses(velocity, ax_conf)
        table_no = vel_no or self._dev.target_vel_no

        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no else None
        resp = self._exec_int('home', ax_num=axis, vel_no=table_no, pat=1)

        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)

        return {'velocity': velocity, 'velocity_pulse': pulse_vel, **resp}

    def read_position(self, axis: int) -> Dict[str, Any]:
        """現在位置を取得する"""
        ax_conf = get_axis_conf(self._cfg, axis)
        resp = self._exec_int('read_position', ax_num=axis)
        pulse = int(resp['pos'])
        unit = pulse_to_length_unit(pulse, ax_conf)
        return {'position': unit, 'position_pulse': pulse, **resp}

    def read_status(self, axis: int) -> Dict[str, Any]:
        """現在のステータスを取得する（モーション中かなど）"""
        return self._exec_int('read_status', ax_num=axis)

    def read_vel_tbl(self, axis: int, vel_no: Optional[int] = None) -> Dict[str, Any]:
        """速度テーブルの情報を取得する"""
        table_no = vel_no or self._dev.target_vel_no
        resp = self._exec_int('read_vel_tbl', ax_num=axis, vel_no=table_no)
        ax_conf = get_axis_conf(self._cfg, axis)

        return {
            'vel_no': table_no,
            'start_velocity': self._convert_pulses_to_velocity(int(resp['start_vel']), ax_conf),
            'max_velocity': self._convert_pulses_to_velocity(int(resp['max_vel']), ax_conf),
            'acc_time': int(resp['acc_time']),
            'acc_type': int(resp.get('acc_type', 0)),
        }

    def write_vel_tbl(
        self,
        axis: int,
        vel_no: int,
        max_velocity: float,
        acc_time: Optional[int] = None,
        dec_time: Optional[int] = None,
        acc_type: Optional[int] = None,
    ) -> Dict[str, Any]:
        """速度テーブルの書き換えを行う"""
        ax_conf = get_axis_conf(self._cfg, axis)
        proc = self._get_processor()
        variant = proc.variant

        max_p = self._convert_velocity_to_pulses(max_velocity, ax_conf)
        start_p = int(max_p * 0.8)

        orig = self._exec_int('read_vel_tbl', ax_num=axis, vel_no=vel_no)
        scale = self._get_vel_table_scaling(orig, max_p)

        acc_time_val = validate_acc_time(acc_time or int(float(orig.get('acc_time', 1)) * scale), ax_conf)

        dec_time_val = (
            validate_dec_time(dec_time or int(float(orig.get('dec_time', acc_time_val)) * scale), ax_conf)
            if 'dec_time' in proc.cmd_map['write_vel_tbl']['args']
            else None
        )

        acc_type_val = (
            validate_acc_type(acc_type if acc_type is not None else 1, variant)
            if 'acc_type' in proc.cmd_map['write_vel_tbl']['args']
            else None
        )

        debug_parts = [f"start: {start_p} (0.8×max)", f"max: {max_p}", f"acc_time: {acc_time_val}"]
        if dec_time_val is not None:
            debug_parts.append(f"dec_time: {dec_time_val}")
        if acc_type_val is not None:
            debug_parts.append(f"acc_type: {acc_type_val}")
        print(f"[DEBUG] write_vel_tbl pulses -> {', '.join(debug_parts)}")

        write_args = {
            'ax_num': axis,
            'vel_no': vel_no,
            'start_vel': start_p,
            'max_vel': max_p,
            'acc_time': acc_time_val,
        }
        if dec_time_val is not None:
            write_args['dec_time'] = dec_time_val
        if acc_type_val is not None:
            write_args['acc_type'] = acc_type_val

        resp = self._exec_int('write_vel_tbl', **write_args)

        result = {
            'start_velocity': self._convert_pulses_to_velocity(start_p, ax_conf),
            'max_velocity': max_velocity,
            'start_pulse': start_p,
            'max_pulse': max_p,
            'acc_time': acc_time_val,
        }
        if dec_time_val is not None:
            result['dec_time'] = dec_time_val
        if acc_type_val is not None:
            result['acc_type'] = acc_type_val
        result.update(resp)
        return result