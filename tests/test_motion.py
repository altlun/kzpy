"""
src/kzpy/tests/test_motion.py

motion.py モジュールの MotionController クラスに対する pytest による単体テストです:
- write_vel_tbl: 速度テーブルの書き込みと引数の型チェック
- _temp_set_velocity: 一時的な速度設定と元に戻すための情報取得
- move_relative: 相対移動コマンドの実行とパラメータ変換の検証
- move_absolute: 絶対位置移動コマンドとパルス単位変換のテスト
- move_stop: モータ停止命令と引数の整数性検証
- home: 原点復帰処理の動作確認と引数チェック
- read_position: 現在位置取得と長さ単位への変換確認
- read_status: ステータス取得処理の動作確認
- read_vel_tbl: 速度テーブル読み取りと単位変換の検証
"""

import pytest
from types import SimpleNamespace
from src.kzpy.motion import MotionController
from types import SimpleNamespace
from src.kzpy._type import DeviceConfig, AxisConfig, SerialConfig  # ← 必要に応じてパス変更

# ===== pytest fixture: 単位変換や設定値取得のモック =====
@pytest.fixture(autouse=True)
def patch_validators(monkeypatch):
    axis_conf = SimpleNamespace(
        pulse_per_unit=10.0,
        min_pulse=0,
        max_pulse=1000,
        max_speed_pulse=500,
        start_velocity_pulse=0,
        acc_time=5,
        acc_type=1
    )
    monkeypatch.setattr('src.kzpy.motion.get_axis_conf', lambda cfg, ax: axis_conf)
    monkeypatch.setattr('src.kzpy.motion.length_unit_to_pulse', lambda length, ax: int(length * ax.pulse_per_unit))
    monkeypatch.setattr('src.kzpy.motion.pulse_to_length_unit', lambda pulse, ax: pulse / ax.pulse_per_unit)
    monkeypatch.setattr('src.kzpy.motion.velocity_unit_to_pulse', lambda vel, ax: int(vel * ax.pulse_per_unit))
    monkeypatch.setattr('src.kzpy.motion.pulse_to_velocity_unit', lambda pulse, ax: pulse / ax.pulse_per_unit)
    yield

# ===== pytest fixture: ensure_idle をスキップ =====
@pytest.fixture(autouse=True)
def skip_idle(monkeypatch):
    import src.kzpy.motion as mmod
    monkeypatch.setattr(mmod.MotionController, 'ensure_idle', lambda self, axis, poll_interval=0.1: None)
    yield


# ===== テスト用ダミーデバイスクラス =====
class DummyDevice:
    def __init__(self):
        # 仮の AxisConfig を2軸分作成（必要に応じて項目追加）
        axes = [
            AxisConfig(
                name="dummy1",
                ax_num=1,
                units="um",
                min_pulse=-1000,
                max_pulse=1000,
                max_speed_pulse=500,
                start_velocity_pulse=0.5,
                pulse_per_unit=0.01,
            ),
            AxisConfig(
                name="dummy2",
                ax_num=2,
                units="um",
                min_pulse=-1000,
                max_pulse=1000,
                max_speed_pulse=500,
                start_velocity_pulse=0.5,
                pulse_per_unit=0.01
            ),
        ]
        # DeviceConfig に準拠した _config を設定
        self._config = DeviceConfig(
            device='dummy',
            axes_sum=2,
            axes=axes,
            serial=SerialConfig(
                baudrate=32000,
                parity="N"
            )
        )


        self.target_vel_no = 1
        self.restore_vel_table = False
        self._processor = SimpleNamespace(
            variant='default',
            cmd_map={'write_vel_tbl': {
                'args': ['ax_num', 'vel_no', 'start_vel', 'max_vel', 'acc_time', 'dec_time', 'acc_type']
            }}
        )
        self.calls = []

    def _execute_command(self, name, **kwargs):
        self.calls.append((name, kwargs.copy()))
        if name == 'read_vel_tbl':
            return {'vel_no': kwargs['vel_no'], 'start_vel': 5, 'max_vel': 5, 'acc_time': 3, 'dec_time': 2, 'acc_type': 2}
        if name in ('move_relative', 'move_absolute'):
            return {'status': 'ok', 'vel_no': kwargs.get('vel_no'), 'length': kwargs.get('length')}
        if name == 'move_stop':
            return {'stopped': True}
        if name == 'home':
            return {'homed': True}
        if name == 'read_position':
            return {'pos': 20}
        if name == 'read_status':
            return {'status': 0}
        if name == 'write_vel_tbl':
            return {'written': True}
        return {}



# ===== MotionController クラスのテスト群 =====

def test_write_vel_tbl():
    """write_vel_tbl: 速度設定の書き込みと型の検証"""
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.write_vel_tbl(axis=1, vel_no=3, max_velocity=2.0, acc_time=4, dec_time=5, acc_type=1)
    assert res['start_pulse'] == 16  # 2.0 * 10 * 0.8
    assert res['max_pulse'] == 20
    assert res['acc_time'] == 4
    assert res['dec_time'] == 5
    assert res['acc_type'] == 1

    assert [c[0] for c in dev.calls[-2:]] == ['read_vel_tbl', 'write_vel_tbl']
    for _, kwargs in dev.calls[-2:]:
        for v in kwargs.values():
            assert isinstance(v, int)


def test_temp_set_velocity():
    """_temp_set_velocity: 一時速度設定と復元用データ取得の検証"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    orig = mc._temp_set_velocity(ax=1, vel_no=1, velocity=2.5)
    assert orig['vel_no'] == 1
    assert orig['start_vel'] == 5
    assert orig['max_vel'] == 5
    assert orig['acc_time'] == 3
    assert orig['acc_type'] == 2
    assert [call[0] for call in dev.calls] == ['read_vel_tbl', 'write_vel_tbl']


def test_move_relative():
    """move_relative: 相対移動のコマンド実行と変換確認"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    result = mc.move_relative(axis=1, length=2.0, velocity=1.5)
    assert result['length_pulse'] == 20
    assert result['velocity_pulse'] == 15
    assert result['length'] == 20
    assert result['status'] == 'ok'
    assert result['vel_no'] == 1


def test_move_absolute():
    """move_absolute: 絶対移動のコマンドと型変換チェック"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    result = mc.move_absolute(axis=2, position=3.5, velocity=2.0)
    assert result['position_pulse'] == 35
    assert result['velocity_pulse'] == 20
    assert result['position'] == 35
    assert result['status'] == 'ok'


def test_move_stop():
    """move_stop: 停止コマンドの発行と型確認"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    res = mc.move_stop(axis=1, pat=7)
    assert res == {'stopped': True}
    name, kwargs = dev.calls[0]
    assert name == 'move_stop'
    assert isinstance(kwargs['ax_num'], int)
    assert isinstance(kwargs['pat'], int)


def test_home():
    """home: 原点復帰命令の発行と速度パルス変換の確認"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    res = mc.home(axis=2, velocity=2.0)
    assert res['velocity_pulse'] == 20
    assert res['velocity'] == 2.0
    assert dev.calls[-1][0] == 'home'


def test_read_position():
    """read_position: 位置読み取りと単位変換の確認"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    res = mc.read_position(axis=1)
    assert res['position'] == 2.0
    assert res['position_pulse'] == 20
    assert res['pos'] == 20


def test_read_status():
    """read_status: ステータス取得処理のテスト"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    res = mc.read_status(axis=1)
    assert res == {'status': 0}
    name, kwargs = dev.calls[0]
    assert name == 'read_status'
    assert isinstance(kwargs['ax_num'], int)


def test_read_vel_tbl():
    """read_vel_tbl: 速度テーブルの読み取りと単位変換の確認"""
    dev = DummyDevice()
    mc = MotionController(dev)
    dev.calls.clear()

    res = mc.read_vel_tbl(axis=1)
    assert res == {
        'vel_no': 1,
        'start_velocity': 0.5,
        'max_velocity': 0.5,
        'acc_time': 3,
        'acc_type': 2,
    }
    assert dev.calls[0][0] == 'read_vel_tbl'
