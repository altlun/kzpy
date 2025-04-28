# src/kzpy/motion.py

from typing import Dict, Any, Optional
from .validate import (
    get_axis_conf,
    length_unit_to_pulse,
    pulse_to_length_unit,
    velocity_unit_to_pulse,
    pulse_to_velocity_unit,
)
from .device import Device

class MotionController:
    def __init__(self, device: Device):
        self._dev = device
        self._cfg = device._config

    def _temp_set_velocity(self, ax: int, vel_no: int, velocity: float) -> Dict[str, Any]:
        """
        一時的に velocity table を書き換え、元の値を返却
        """
        axis = get_axis_conf(self._cfg, ax)
        vel_pulse = velocity_unit_to_pulse(velocity, axis)

        orig = self._dev._execute_command('read_vel_tbl', ax_num=ax, vel_no=vel_no)
        # start_vel, max_vel を同じ値に更新
        self._dev._execute_command(
            'write_vel_tbl',
            ax_num=ax,
            vel_no=vel_no,
            start_vel=int(vel_pulse),
            max_vel=int(vel_pulse),
            acc_time=int(orig['acc_time']),
            acc_type=int(orig['acc_type']),
        )
        return orig

    def move_relative(
        self,
        axis: int,
        length: float,
        velocity: float,
        vel_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_len = length_unit_to_pulse(length, ax_conf)
        table_no = vel_no if vel_no is not None else self._dev.target_vel_no

        orig = None
        if table_no is not None:
            orig = self._temp_set_velocity(axis, table_no, velocity)

        resp = self._dev._execute_command(
            'move_relative',
            ax_num=axis,
            vel_no=table_no,
            length=pulse_len,
            pat=1,
        )

        if orig and self._dev.restore_vel_table:
            self._dev._execute_command(
                'write_vel_tbl',
                ax_num=axis,
                vel_no=orig['vel_no'],
                start_vel=int(orig['start_vel']),
                max_vel=int(orig['max_vel']),
                acc_time=int(orig['acc_time']),
                acc_type=int(orig['acc_type']),
            )

        return {
            'length': length,
            'length_pulse': pulse_len,
            'velocity': velocity,
            'velocity_pulse': velocity_unit_to_pulse(velocity, ax_conf),
            **resp
        }

    def move_absolute(
        self,
        axis: int,
        position: float,
        velocity: float,
        vel_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        pulse_pos = length_unit_to_pulse(position, ax_conf)
        table_no = vel_no if vel_no is not None else self._dev.target_vel_no

        orig = None
        if table_no is not None:
            orig = self._temp_set_velocity(axis, table_no, velocity)

        resp = self._dev._execute_command(
            'move_absolute',
            ax_num=axis,
            vel_no=table_no,
            length=pulse_pos,
            pat=1,
        )

        if orig and self._dev.restore_vel_table:
            self._dev._execute_command(
                'write_vel_tbl',
                ax_num=axis,
                vel_no=orig['vel_no'],
                start_vel=int(orig['start_vel']),
                max_vel=int(orig['max_vel']),
                acc_time=int(orig['acc_time']),
                acc_type=int(orig['acc_type']),
            )

        return {
            'position': position,
            'position_pulse': pulse_pos,
            'velocity': velocity,
            'velocity_pulse': velocity_unit_to_pulse(velocity, ax_conf),
            **resp
        }

    def move_stop(self, axis: int, pat: int = 1) -> Dict[str, Any]:
        return self._dev._execute_command('move_stop', ax_num=axis, pat=pat)

    def home(
        self,
        axis: int,
        velocity: float,
        vel_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        vel_pulse = velocity_unit_to_pulse(velocity, ax_conf)
        table_no = vel_no if vel_no is not None else self._dev.target_vel_no

        orig = None
        if table_no is not None:
            orig = self._temp_set_velocity(axis, table_no, velocity)

        resp = self._dev._execute_command(
            'home',
            ax_num=axis,
            vel_no=table_no,
            pat=1,
        )

        if orig and self._dev.restore_vel_table:
            self._dev._execute_command(
                'write_vel_tbl',
                ax_num=axis,
                vel_no=orig['vel_no'],
                start_vel=int(orig['start_vel']),
                max_vel=int(orig['max_vel']),
                acc_time=int(orig['acc_time']),
                acc_type=int(orig['acc_type']),
            )

        return {
            'velocity': velocity,
            'velocity_pulse': vel_pulse,
            **resp
        }

    def read_position(self, axis: int) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        resp = self._dev._execute_command('read_position', ax_num=axis)
        pulse = int(resp['pos'])
        unit = pulse_to_length_unit(pulse, ax_conf)
        return {
            'position': unit,
            'position_pulse': pulse,
            **resp
        }

    def read_status(self, axis: int) -> Dict[str, Any]:
        return self._dev._execute_command('read_status', ax_num=axis)

    def read_vel_tbl(self, axis: int, vel_no: Optional[int] = None) -> Dict[str, Any]:
        table_no = vel_no if vel_no is not None else self._dev.target_vel_no
        resp = self._dev._execute_command('read_vel_tbl', ax_num=axis, vel_no=table_no)
        ax_conf = get_axis_conf(self._cfg, axis)
        start_u = pulse_to_velocity_unit(int(resp['start_vel']), ax_conf)
        max_u   = pulse_to_velocity_unit(int(resp['max_vel']), ax_conf)
        return {
            'vel_no': table_no,
            'start_velocity': start_u,
            'max_velocity': max_u,
            'acc_time': int(resp['acc_time']),
            'acc_type': int(resp['acc_type']),
        }

    def write_vel_tbl(
        self,
        axis: int,
        vel_no: int,
        start_velocity: float,
        max_velocity: float,
        acc_time: int,
        acc_type: int,
    ) -> Dict[str, Any]:
        ax_conf = get_axis_conf(self._cfg, axis)
        start_p = velocity_unit_to_pulse(start_velocity, ax_conf)
        max_p   = velocity_unit_to_pulse(max_velocity, ax_conf)
        resp = self._dev._execute_command(
            'write_vel_tbl',
            ax_num=axis,
            vel_no=vel_no,
            start_vel=start_p,
            max_vel=max_p,
            acc_time=acc_time,
            acc_type=acc_type,
        )
        return {
            'start_velocity': start_velocity,
            'start_pulse': start_p,
            'max_velocity': max_velocity,
            'max_pulse': max_p,
            **resp
        }
