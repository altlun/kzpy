import pytest
from types import SimpleNamespace

import serial
from serial.tools import list_ports

from src.kzpy.device import Device
from src.kzpy._type import DeviceConfig

# ===== Mock クラス定義 =====
# DummySerialIO: シリアル通信を模倣し、send_and_receive の挙動を制御
class DummySerialIO:
    def __init__(self, port, baudrate, timeout):
        # ポート名、ボーレート、タイムアウトを保持
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None          # 実シリアルオブジェクトのプレースホルダ
        self.opened = False      # open() 呼び出しフラグ
        self.closed = False      # close() 呼び出しフラグ
        self.sent = []           # 送信したデータの履歴

    def open(self):
        # open を呼ぶと opened を True に
        self.opened = True

    def close(self):
        # close を呼ぶと closed を True に
        self.closed = True

    def send_and_receive(self, data: bytes):
        # 送信データを記録
        self.sent.append(data)
        # インスタンスにあらかじめ設定された response 属性を返却
        if hasattr(self, 'response'):
            return self.response
        # デフォルトは OK:TestDevice
        return b"OK:TestDevice"

# DummyCmdProc: コマンド生成とレスポンス解析を模倣
class DummyCmdProc:
    def __init__(self):
        self.commands = []  # generate_command 呼び出し履歴

    def generate_command(self, name, **kwargs):
        # 呼び出しを記録し、任意のバイト列を返す
        self.commands.append((name, kwargs))
        return b"CMD"

    def parse_response(self, text: str, name: str):
        # identify コマンド時は OK:DeviceName 形式をパースして dev_name を返す
        if name == "identify":
            parts = text.split(':', 1)
            dev = parts[1] if len(parts) > 1 else ""
            return {"dev_name": dev}
        # その他はそのまま parsed キーで返却
        return {"parsed": text}

# DummyPortInfo: serial.tools.list_ports.comports() が返すオブジェクトを模倣
class DummyPortInfo:
    def __init__(self, device):
        self.device = device

# ===== pytest フィクスチャ: グローバルモンキーパッチ =====
@pytest.fixture(autouse=True)
def patch_config_loader(monkeypatch):
    # load_device_config をモックし、DeviceConfig 相当のオブジェクトを返す
    dummy_conf = SimpleNamespace(
        device="TestDevice",
        serial=SimpleNamespace(baudrate=9600, parity='N')
    )
    monkeypatch.setattr(
        'src.kzpy.device.load_device_config',
        lambda path, default: dummy_conf
    )
    # SerialIO と CommandProcessor をモッククラスに差し替え
    monkeypatch.setattr('src.kzpy.device.SerialIO', DummySerialIO)
    monkeypatch.setattr('src.kzpy.device.CommandProcessor', DummyCmdProc)
    # serial.Serial の実ポートオープンを防ぐ
    class DummyPySerial:
        def __init__(self, *args, **kwargs):
            pass
    monkeypatch.setattr(serial, 'Serial', DummyPySerial)
    yield

# ===== テスト: Device.connect の成功パターン =====
def test_connect_success(monkeypatch):
    # list_ports.comports() を 1 つのポートに設定
    monkeypatch.setattr(list_ports, 'comports', lambda: [DummyPortInfo('/dev/ttyUSB0')])

    # SerialIO インスタンスにデバイス名 OK:TestDevice を返すよう設定
    def mk_serial(port, baudrate, timeout):
        inst = DummySerialIO(port, baudrate, timeout)
        inst.response = b"OK:TestDevice"  # identify コマンドのレスポンスを固定
        return inst
    monkeypatch.setattr('src.kzpy.device.SerialIO', mk_serial)

    # 実行: 成功すると Device インスタンスを返す
    device = Device.connect(path=None, default='any', timeout=0.1)
    assert isinstance(device, Device)
    assert device._serial.port == '/dev/ttyUSB0'
    # デフォルトとターゲットの速度テーブル番号が初期値になる
    assert device.default_vel_no == 0
    assert device.target_vel_no == 0

# ===== テスト: ポート無しエラー =====
def test_connect_no_ports_raises(monkeypatch):
    # ポートリストを空に設定
    monkeypatch.setattr(list_ports, 'comports', lambda: [])

    # RuntimeError が発生することを期待
    with pytest.raises(RuntimeError) as excinfo:
        Device.connect()
    assert "Could not connect to device" in str(excinfo.value)

# ===== テスト: 1つ目非一致、2つ目一致パターン =====
def test_connect_skip_non_matching_and_find_matching(monkeypatch):
    calls = {'count': 0}

    # SerialIO のファクトリ: ポートによって異なる response を設定し、呼び出し回数をカウント
    def serial_factory(port, baudrate, timeout):
        inst = DummySerialIO(port, baudrate, timeout)
        # 1つ目のポートは OtherDevice、2つ目は TestDevice を返す
        inst.response = b"OK:OtherDevice" if port == '/dev/ttyUSB0' else b"OK:TestDevice"
        # send_and_receive をラップしてカウントをインクリメント
        orig = inst.send_and_receive
        def counted(data):
            calls['count'] += 1
            return orig(data)
        inst.send_and_receive = counted
        return inst

    monkeypatch.setattr('src.kzpy.device.SerialIO', serial_factory)
    monkeypatch.setattr(list_ports, 'comports', lambda: [DummyPortInfo('/dev/ttyUSB0'), DummyPortInfo('/dev/ttyUSB1')])

    device = Device.connect(timeout=0.1)
    # 2 回 identify が呼ばれていることを検証
    assert calls['count'] == 2
    # 最終的に 2 番目のポートが選択されている
    assert device._serial.port == '/dev/ttyUSB1'

# ===== テスト: disconnect =====
def test_disconnect_closes_serial(monkeypatch):
    # 手動で DummySerialIO インスタンスを生成し、close() を検証
    dummy_serial = DummySerialIO('/dev/tty', 9600, 0.1)
    cmd_proc = DummyCmdProc()
    cfg = SimpleNamespace(
        device="TestDevice",
        serial=SimpleNamespace(baudrate=9600, parity='N')
    )
    device = Device(cfg, dummy_serial, cmd_proc)
    device.disconnect()
    assert dummy_serial.closed is True  # close メソッドが呼ばれているか

# ===== テスト: get_information と _execute_command =====
def test_get_information_and_execute(monkeypatch):
    # get_information() 経由で identify コマンドの送受信とパースを検証
    dummy_serial = DummySerialIO('/dev/tty', 9600, 0.1)
    cmd_proc = DummyCmdProc()
    cfg = SimpleNamespace(
        device="TestDevice",
        serial=SimpleNamespace(baudrate=9600, parity='N')
    )
    device = Device(cfg, dummy_serial, cmd_proc)

    info = device.get_information()
    # generate_command と parse_response が正しく呼ばれていること
    assert cmd_proc.commands[0][0] == 'identify'
    assert info.get('dev_name') == 'TestDevice'  # レスポンスの解析結果を検証
