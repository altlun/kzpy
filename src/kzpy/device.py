"""
src/kzpy/device.py
config/*.json から設定を読み込み、DeviceConfig モデルを元にシリアルデバイスとの通信を管理します。
- デバイスの自動検出や接続確認、コマンド送信・受信処理を提供
"""

import serial
from typing import Optional, Dict, Any
from serial.tools import list_ports

from .config_loader import load_device_config
from ._serial import SerialIO
from ._command import CommandProcessor
from ._type import DeviceConfig

class Device:
    """
    デバイスとの通信を管理するクラス
    - 設定ファイルの読み込み、シリアル通信、コマンド生成・解析を統合
    """

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
        # 設定情報、シリアル通信オブジェクト、コマンドプロセッサを保持
        self._config = config
        self._serial = serial_io
        self._cmd = cmd_proc

        # 速度テーブルに関する設定
        self.default_vel_no = default_vel_no
        self.restore_vel_table = restore_vel_table
        self.target_vel_no = target_vel_no if target_vel_no is not None else default_vel_no

    @classmethod
    def connect(
        cls,
        path: Optional[str] = None,
        variant: str = "aries",  
        timeout: float = 0.5,
        default_vel_no: int = 0,
        restore_vel_table: bool = True,
        target_vel_no: Optional[int] = None,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        parity: Optional[str] = None,
    ) -> "Device":
        """
        デバイスへ接続を試み、成功すれば Device インスタンスを返す
        - 設定ファイルを読み込み、接続候補ポートに順に接続を試行
        - `identify` コマンドで対象デバイスか確認
        - 明示的なポート指定がある場合はそれを優先
        """
        # 機種ごとの設定ファイル読み込み
        config = load_device_config(path, variant)
        cmd_proc = CommandProcessor(variant=variant)

        # ポート/ボーレートが指定されている場合はそれを使って接続
        if port is not None and baudrate is not None:
            used_parity = parity if parity is not None else config.serial.parity
            print(f"[Override] 試行中 -> port={port}, baudrate={baudrate}, parity={used_parity}")
            try:
                serial_io = SerialIO(port, baudrate, timeout)
                ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout,
                    parity=used_parity,
                )
                serial_io.ser = ser

                # identify コマンドで接続対象が一致するか確認
                cmd = cmd_proc.generate_command("identify")
                raw = serial_io.send_and_receive(cmd)
                parsed = cmd_proc.parse_response(
                    raw.decode('ascii', errors='ignore').strip(), "identify"
                )

                if parsed.get("dev_name") == config.device:
                    print(f"[Override] 接続成功 -> port {port}")
                    return cls(
                        config,
                        serial_io,
                        cmd_proc,
                        default_vel_no=default_vel_no,
                        restore_vel_table=restore_vel_table,
                        target_vel_no=target_vel_no,
                    )
                else:
                    print(f"[Override] デバイス名不一致: 期待={config.device}, 実際={parsed.get('dev_name')}")
                    serial_io.close()
                    raise RuntimeError(f"Overrideポート '{port}' でデバイスが一致しませんでした。")
            except Exception as e:
                print(f"[Override] 接続失敗 -> port={port}, エラー={e}")
                raise

        # 指定がなければ、全ポートをスキャンして接続を試行
        for port_info in list_ports.comports():
            port_candidate = port_info.device
            used_baud = config.serial.baudrate
            used_parity = config.serial.parity
            print(f"[Scan] 試行中 -> port={port_candidate}, baudrate={used_baud}, parity={used_parity}")
            try:
                serial_io = SerialIO(port_candidate, used_baud, timeout)
                ser = serial.Serial(
                    port=port_candidate,
                    baudrate=used_baud,
                    timeout=timeout,
                    parity=used_parity,
                )
                serial_io.ser = ser

                cmd = cmd_proc.generate_command("identify")
                raw = serial_io.send_and_receive(cmd)
                parsed = cmd_proc.parse_response(
                    raw.decode('ascii', errors='ignore').strip(), "identify"
                )

                if parsed.get("dev_name") == config.device:
                    print(f"[Scan] 接続成功 -> port {port_candidate}")
                    return cls(
                        config,
                        serial_io,
                        cmd_proc,
                        default_vel_no=default_vel_no,
                        restore_vel_table=restore_vel_table,
                        target_vel_no=target_vel_no,
                    )
                else:
                    print(f"[Scan] デバイス不一致 on {port_candidate}: 期待={config.device}, 実際={parsed.get('dev_name')}")
                    serial_io.close()
            except Exception as e:
                print(f"[Scan] 接続失敗 -> port={port_candidate}, エラー={e}")
                try:
                    serial_io.close()
                except Exception:
                    pass
                continue

        # すべての接続試行に失敗した場合は例外を投げる
        raise RuntimeError(f"デバイス '{config.device}' に接続できませんでした。")

    def disconnect(self) -> None:
        """
        シリアル接続を明示的に閉じる
        """
        self._serial.close()

    def get_information(self) -> Dict[str, Any]:
        """
        identify コマンドを実行し、デバイス名とバージョン情報を取得
        """
        return self._execute_command("identify")

    def _execute_command(self, command_name: str, **kwargs) -> Dict[str, Any]:
        """
        任意のコマンドを実行し、レスポンスの解析結果を返す
        - シリアルポートのオープン確認
        - 送受信時間の計測とデバッグログ出力
        """
        import time
        self._serial.open()
        cmd_bytes = self._cmd.generate_command(command_name, **kwargs)

        t0 = time.time()
        raw = self._serial.send_and_receive(cmd_bytes)
        t1 = time.time()

        print(f"[DEBUG] `{command_name}` raw bytes: {raw}")
        try:
            decoded = raw.decode('ascii', errors='ignore').strip()
            print(f"[DEBUG] `{command_name}` decoded text: {decoded}")
        except Exception:
            pass

        print(f"[DEBUG] `{command_name}` RTT: {(t1-t0)*1000:.1f} ms")
        return self._cmd.parse_response(decoded, command_name)
