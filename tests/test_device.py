"""
src/kzpy/tests/test_device.py

device.py モジュールの Device クラスに対する pytest による単体テストです:
- connect: COMポートを用いたデバイスへの接続処理
- disconnect: シリアル接続の切断
- get_information: identify コマンドによるデバイス情報取得
"""

import pytest
from types import SimpleNamespace
import serial
from serial.tools import list_ports

from src.kzpy.device import Device
from src.kzpy._type import DeviceConfig

# ===== モック定義 =====

# シリアル通信の模擬クラス
class DummySerialIO:
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.opened = False
        self.closed = False
        self.sent = []

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def send_and_receive(self, data: bytes):
        self.sent.append(data)
        return getattr(self, 'response', b"OK:TestDevice")

# コマンド処理の模擬クラス
class DummyCmdProc:
    def __init__(self, variant=None):
        self.variant = variant
        self.commands = []

    def generate_command(self, name, **kwargs):
        self.commands.append((name, kwargs))
        return b"CMD"

    def parse_response(self, text: str, name: str):
        if name == "identify":
            parts = text.split(':', 1)
            return {"dev_name": parts[1] if len(parts) > 1 else ""}
        return {"parsed": text}

# COMポート情報のモック
class DummyPortInfo:
    def __init__(self, device):
        self.device = device

# ===== フィクスチャ（自動適用） =====

# device.py 内部の依存をすべてモックに置き換える
@pytest.fixture(autouse=True)
def patch_config_loader(monkeypatch):
    dummy_conf = SimpleNamespace(
        device="TestDevice",
        serial=SimpleNamespace(baudrate=9600, parity='N')
    )
    monkeypatch.setattr(
        'src.kzpy.device.load_device_config',
        lambda path, variant: dummy_conf
    )
    monkeypatch.setattr('src.kzpy.device.SerialIO', DummySerialIO)
    monkeypatch.setattr('src.kzpy.device.CommandProcessor', DummyCmdProc)

    class DummyPySerial:
        def __init__(self, *args, **kwargs): pass

    monkeypatch.setattr(serial, 'Serial', DummyPySerial)
    yield

# ===== テストケース群 =====

# 正常に接続されることを確認
def test_connect_success(monkeypatch):
    monkeypatch.setattr(list_ports, 'comports', lambda: [DummyPortInfo('/dev/ttyUSB0')])

    def mk_serial(port, baudrate, timeout):
        inst = DummySerialIO(port, baudrate, timeout)
        inst.response = b"OK:TestDevice"
        return inst

    monkeypatch.setattr('src.kzpy.device.SerialIO', mk_serial)

    device = Device.connect(path=None, variant='any', timeout=0.1)
    assert isinstance(device, Device)
    assert device._serial.port == '/dev/ttyUSB0'
    assert device.default_vel_no == 0
    assert device.target_vel_no == 0

# ポートがまったく存在しない場合、例外が発生することを確認
def test_connect_no_ports_raises():
    import src.kzpy.device as mod
    original_comports = list_ports.comports
    list_ports.comports = lambda: []

    with pytest.raises(RuntimeError) as excinfo:
        Device.connect()

    msg = str(excinfo.value)
    assert "接続できませんでした" in msg
    assert "TestDevice" in msg

    list_ports.comports = original_comports  # 元に戻す

# 最初のポートが不一致、2つ目で一致 → 接続成功
def test_connect_skip_non_matching_and_find_matching(monkeypatch):
    calls = {'count': 0}

    def serial_factory(port, baudrate, timeout):
        inst = DummySerialIO(port, baudrate, timeout)
        inst.response = b"OK:OtherDevice" if port == '/dev/ttyUSB0' else b"OK:TestDevice"

        orig = inst.send_and_receive

        def counted(data):
            calls['count'] += 1
            return orig(data)

        inst.send_and_receive = counted
        return inst

    monkeypatch.setattr('src.kzpy.device.SerialIO', serial_factory)
    monkeypatch.setattr(list_ports, 'comports', lambda: [DummyPortInfo('/dev/ttyUSB0'), DummyPortInfo('/dev/ttyUSB1')])

    device = Device.connect(timeout=0.1)
    assert calls['count'] == 2
    assert device._serial.port == '/dev/ttyUSB1'

# disconnect により close が呼ばれることを確認
def test_disconnect_closes_serial():
    dummy_serial = DummySerialIO('/dev/tty', 9600, 0.1)
    cmd_proc = DummyCmdProc()
    cfg = SimpleNamespace(device="TestDevice", serial=SimpleNamespace(baudrate=9600, parity='N'))

    device = Device(cfg, dummy_serial, cmd_proc)
    device.disconnect()
    assert dummy_serial.closed is True

# get_information 経由で identify コマンドが発行され、レスポンスが正しく処理されることを確認
def test_get_information_and_execute():
    dummy_serial = DummySerialIO('/dev/tty', 9600, 0.1)
    cmd_proc = DummyCmdProc()
    cfg = SimpleNamespace(device="TestDevice", serial=SimpleNamespace(baudrate=9600, parity='N'))

    device = Device(cfg, dummy_serial, cmd_proc)
    info = device.get_information()

    assert cmd_proc.commands[0][0] == 'identify'
    assert info.get('dev_name') == 'TestDevice'
