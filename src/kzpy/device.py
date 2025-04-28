# src/kzpy/device.py

import serial
from typing import Optional, Dict, Any
from serial.tools import list_ports

from .config_loader import load_device_config
from ._serial import SerialIO
from ._command import CommandProcessor
from ._type import DeviceConfig

class Device:
    def __init__(
        self,
        config: DeviceConfig,
        serial_io: SerialIO,
        cmd_proc: CommandProcessor,
        *,
        default_vel_no: int = 0,
        restore_vel_table: bool = True,
        target_vel_no: Optional[int] = None,
    ):
        self._config = config
        self._serial = serial_io
        self._cmd = cmd_proc

        # velocity table settings
        self.default_vel_no = default_vel_no
        self.restore_vel_table = restore_vel_table
        # 最終的に使うテーブル番号
        self.target_vel_no = target_vel_no if target_vel_no is not None else default_vel_no

    @classmethod
    def connect(
        cls,
        path: Optional[str] = None,
        default: str = "aries",
        timeout: float = 0.5,
        default_vel_no: int = 0,
        restore_vel_table: bool = True,
        target_vel_no: Optional[int] = None,
    ) -> "Device":
        config = load_device_config(path, default)
        cmd_proc = CommandProcessor()

        for port_info in list_ports.comports():
            port = port_info.device
            try:
                serial_io = SerialIO(port, config.serial.baudrate, timeout)
                ser = serial.Serial(
                    port=port,
                    baudrate=config.serial.baudrate,
                    timeout=timeout,
                    parity=config.serial.parity,
                )
                serial_io.ser = ser

                # デバイス識別
                cmd = cmd_proc.generate_command("identify")
                raw = serial_io.send_and_receive(cmd)
                parsed = cmd_proc.parse_response(raw.decode('ascii', errors='ignore').strip(), "identify")

                if parsed.get("dev_name") == config.device:
                    return cls(
                        config,
                        serial_io,
                        cmd_proc,
                        default_vel_no=default_vel_no,
                        restore_vel_table=restore_vel_table,
                        target_vel_no=target_vel_no,
                    )

                serial_io.close()
            except Exception:
                try:
                    serial_io.close()
                except Exception:
                    pass
                continue

        raise RuntimeError(f"Could not connect to device '{config.device}' on any serial port.")

    def disconnect(self) -> None:
        self._serial.close()

    def get_information(self) -> Dict[str, Any]:
        """
        identify コマンドで返ってくる dev_name, dev_var をそのまま返却
        """
        return self._execute_command("identify")

    def _execute_command(self, command_name: str, **kwargs) -> Dict[str, Any]:
        """
        共通送受信 + パース
        """
        self._serial.open()
        cmd_bytes = self._cmd.generate_command(command_name, **kwargs)
        raw = self._serial.send_and_receive(cmd_bytes)
        text = raw.decode('ascii', errors='ignore').strip()
        return self._cmd.parse_response(text, command_name)
