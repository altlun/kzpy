"""
src/kzpy/device.py

config/*.json から設定を読み込み、DeviceConfig モデルを元にシリアルデバイスとの通信を管理します。
- デバイスの自動検出や接続確認、コマンド送信・受信処理を提供
- 起動時に速度テーブル0をデフォルトで初期化し、操作後は元に戻す
"""

from typing import Dict, Any, Optional, Callable
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
from ._type import DeviceConfig
import functools
import time

START_VEL = 5
ACC_TIME = 5
DEC_TIME = 5

def log_io(temp_methods: Optional[tuple] = None) -> Callable:
    """
    各メソッドの呼び出し前後に print するデコレーター。
    temp_methods に含まれるメソッドは temp_change=True として表示。
    """
    temp_methods = temp_methods or ()
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            is_temp = func.__name__ in temp_methods
            print(f"[CALL] {func.__name__}  args={args}, kwargs={kwargs}, temp_change={is_temp}")
            result = func(self, *args, **kwargs)
            print(f"[RETURN] {func.__name__} → {result}")
            return result
        return wrapper
    return decorator


class MotionController:
    def __init__(self, device: Device):
        """
        デバイスインスタンスを受け取り、構成情報を保持
        Pydantic の DeviceConfig 型を想定し、axes リストから
        起動時に全軸の vel_no=0 をデフォルトで初期化
        """
        self._dev = device
        cfg = device._config
        # 辞書として渡された場合は DeviceConfig にパース
        if not isinstance(cfg, DeviceConfig):
            cfg = DeviceConfig(**cfg)
        self._cfg: DeviceConfig = cfg

        # 各軸を初期化
        for axis_conf in self._cfg.axes:
            axis_num = axis_conf.ax_num
            try:
                # write_vel_tbl は内部で単位変換を行うため float/int 混在可
                self.write_vel_tbl(
                    axis=axis_num,
                    vel_no=0,
                    max_velocity=1000,
                    acc_time=ACC_TIME,
                    dec_time=DEC_TIME,
                    acc_type=2
                )
            except Exception as e:
                print(f"[WARN] axis {axis_num} default vel table init failed: {e}")


    def _exec_int(self, name: str, **kwargs) -> Dict[str, Any]:
        """キーワード引数を整数に変換し、コマンドを実行。送受信を print でログ出力"""
        send_args = {k: int(v) for k, v in kwargs.items()}
        print(f"[CMD SEND] {name} {send_args}")
        resp = self._dev._execute_command(name, **send_args)
        print(f"[CMD RECV] {name} → {resp}")
        return resp

    def ensure_idle(self, axis: int, poll_interval: float = 0.1):
        """コマンド実行前後に呼び出して、デバイスがアイドル状態(status=="0")になるまで待機"""
        while True:
            sta = self.read_status(axis=axis)
            if sta.get('status') == '0':
                break
            print(f"[ENSURE_IDLE] waiting, status={sta.get('status')}")
            time.sleep(poll_interval)

    def _get_processor(self):
        return getattr(self._dev, '_cmd', None) or getattr(self._dev, '_processor', None)

    def _convert_velocity_to_pulses(self, velocity: float, ax_conf: dict) -> int:
        return velocity_unit_to_pulse(velocity, ax_conf)

    def _convert_pulses_to_velocity(self, pulses: int, ax_conf: dict) -> float:
        return pulse_to_velocity_unit(pulses, ax_conf)

    def _get_vel_table_scaling(self, orig: dict, max_pulse: int) -> float:
        orig_max = int(orig.get('max_vel', max_pulse))
        return max_pulse / orig_max if orig_max else 1.0

    def _temp_set_velocity(self, ax: int, vel_no: int, velocity: float) -> Dict[str, Any]:
        """一時的に速度テーブルを書き換える"""
        axis_cfg = get_axis_conf(self._cfg, ax)
        max_pulse = self._convert_velocity_to_pulses(velocity, axis_cfg)
        start_pulse = int(START_VEL)

        proc = self._get_processor()
        # 常に現在のテーブルを読み出す
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
        print(f"[DEBUG] Restoring write_vel_tbl variant={getattr(proc, 'variant', None)}, args={restore_args}")
        self._exec_int('write_vel_tbl', **restore_args)

    @log_io(temp_methods=('move_relative_sync','move_absolute_sync','home_sync'))
    def move_relative(self, axis: int, length: float, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        return self.move_relative_sync(axis, length, velocity, vel_no)

    def move_relative_sync(
        self, axis: int, length: float, velocity: float,
        vel_no: Optional[int] = None, buffer: float = 0.2
    ) -> Dict[str, Any]:
        self.ensure_idle(axis)
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_len = length_unit_to_pulse(length, ax_conf)
        table_no = vel_no or self._dev.target_vel_no
        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no is not None else None
        resp = self._exec_int('move_relative', ax_num=axis, vel_no=table_no, length=pulse_len, pat=1)
        time.sleep((abs(length) / velocity) + buffer)
        self.ensure_idle(axis)
        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)
        return {'length_pulse': pulse_len, 'velocity': velocity, 'velocity_pulse': self._convert_velocity_to_pulses(velocity, ax_conf), **resp}

    @log_io(temp_methods=('move_relative_sync','move_absolute_sync','home_sync'))
    def move_absolute(self, axis: int, position: float, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        return self.move_absolute_sync(axis, position, velocity, vel_no)

    def move_absolute_sync(
        self, axis: int, position: float, velocity: float,
        vel_no: Optional[int] = None, buffer: float = 0.2
    ) -> Dict[str, Any]:
        self.ensure_idle(axis)
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_pos = length_unit_to_pulse(position, ax_conf)
        table_no = vel_no or self._dev.target_vel_no
        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no is not None else None
        resp = self._exec_int('move_absolute', ax_num=axis, vel_no=table_no, length=pulse_pos, pat=1)
        time.sleep((abs(position) / velocity) + buffer)
        self.ensure_idle(axis)
        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)
        return {'position': resp.get('length'), 'position_pulse': pulse_pos, 'velocity': velocity, 'velocity_pulse': self._convert_velocity_to_pulses(velocity, ax_conf), **resp}

    @log_io(temp_methods=('move_relative_sync','move_absolute_sync','home_sync'))
    def home(self, axis: int, velocity: float, vel_no: Optional[int] = None) -> Dict[str, Any]:
        return self.home_sync(axis, velocity, vel_no)

    def home_sync(self, axis: int, velocity: float, vel_no: Optional[int] = None, buffer: float = 0.2) -> Dict[str, Any]:
        self.ensure_idle(axis)
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_vel = self._convert_velocity_to_pulses(velocity, ax_conf)
        table_no = vel_no or self._dev.target_vel_no
        orig = self._temp_set_velocity(axis, table_no, velocity) if table_no is not None else None
        resp = self._exec_int('home', ax_num=axis, vel_no=table_no, pat=1)
        time.sleep(1.0 + buffer)
        self.ensure_idle(axis)
        if orig and self._dev.restore_vel_table:
            self._restore_vel_tbl(orig)
        return {'velocity': velocity, 'velocity_pulse': pulse_vel, **resp}

    @log_io()
    def move_stop(self, axis: int, pat: int = 1) -> Dict[str, Any]:
        return self._exec_int('move_stop', ax_num=axis, pat=pat)

    @log_io()
    def read_position(self, axis: int) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        resp = self._exec_int('read_position', ax_num=axis)
        pulse = int(resp['pos'])
        unit = pulse_to_length_unit(pulse, ax_conf)
        return {'position': unit, 'position_pulse': pulse, **resp}

    @log_io()
    def read_status(self, axis: int) -> Dict[str, Any]:
        return self._exec_int('read_status', ax_num=axis)

    @log_io()
    def read_vel_tbl(self, axis: int, vel_no: Optional[int] = None) -> Dict[str, Any]:
        table_no = vel_no or self._dev.target_vel_no
        resp = self._exec_int('read_vel_tbl', ax_num=axis, vel_no=table_no)
        ax_conf = get_axis_conf(self._cfg, axis)
        return {'vel_no': table_no, 'start_velocity': self._convert_pulses_to_velocity(int(resp['start_vel']), ax_conf), 'max_velocity': self._convert_pulses_to_velocity(int(resp['max_vel']), ax_conf), 'acc_time': int(resp['acc_time']), 'acc_type': int(resp.get('acc_type', 0))}

    @log_io()
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

        # 読み取り
        orig = self._exec_int('read_vel_tbl', ax_num=axis, vel_no=vel_no)
        scale = self._get_vel_table_scaling(orig, velocity_unit_to_pulse(max_velocity, ax_conf))

        acc_time_val = validate_acc_time(acc_time or int(float(orig.get('acc_time', 1)) * scale), ax_conf)
        dec_time_val = (
            validate_dec_time(dec_time or int(float(orig.get('dec_time', acc_time_val)) * scale), ax_conf)
            if 'dec_time' in proc.cmd_map['write_vel_tbl']['args'] else None
        )
        acc_type_val = (
            validate_acc_type(acc_type if acc_type is not None else 1, getattr(proc, 'variant', None))
            if 'acc_type' in proc.cmd_map['write_vel_tbl']['args'] else None
        )

        debug_parts = [f"start: {int(orig.get('start_vel', 0))}", f"max: {velocity_unit_to_pulse(max_velocity, ax_conf)}", f"acc_time: {acc_time_val}"]
        if dec_time_val is not None:
            debug_parts.append(f"dec_time: {dec_time_val}")
        if acc_type_val is not None:
            debug_parts.append(f"acc_type: {acc_type_val}")
        print(f"[DEBUG] write_vel_tbl pulses -> {', '.join(debug_parts)}")

        write_args = {'ax_num': axis, 'vel_no': vel_no, 'start_vel': int(START_VEL), 'max_vel': int(velocity_unit_to_pulse(max_velocity, ax_conf)), 'acc_time': acc_time_val}
        if dec_time_val is not None:
            write_args['dec_time'] = dec_time_val
        if acc_type_val is not None:
            write_args['acc_type'] = acc_type_val

        resp = self._exec_int('write_vel_tbl', **write_args)
        result = {'start_velocity': self._convert_pulses_to_velocity(write_args['start_vel'], ax_conf), 'max_velocity': max_velocity, 'start_pulse': write_args['start_vel'], 'max_pulse': write_args['max_vel'], 'acc_time': acc_time_val}
        if dec_time_val is not None:
            result['dec_time'] = dec_time_val
        if acc_type_val is not None:
            result['acc_type'] = acc_type_val
        result.update(resp)
        return result
