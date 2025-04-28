import pytest
from types import SimpleNamespace

from src.kzpy.motion import MotionController

# ===== pytest フィクスチャ: バリデーション関数のモック =====
@pytest.fixture(autouse=True)
def patch_validators(monkeypatch):
    # get_axis_conf は任意の config・軸番号から同じ AxisConfig を返す
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

# ===== Dummy デバイスクラス =====
class DummyDevice:
    def __init__(self):
        self._config = SimpleNamespace()  # 実際は get_axis_conf の引数だが無視される
        self.target_vel_no = 1
        self.restore_vel_table = True
        self.calls = []

    def _execute_command(self, name, **kwargs):
        # 呼び出し記録
        self.calls.append((name, kwargs.copy()))
        # コマンドごとの固定レスポンスを返却
        if name == 'read_vel_tbl':
            return {
                'vel_no': kwargs['vel_no'],
                'start_vel': 5,
                'max_vel': 5,
                'acc_time': 3,
                'acc_type': 2,
            }
        if name in ('move_relative', 'move_absolute'):
            return {'status': 'ok', 'vel_no': kwargs.get('vel_no'), 'length': kwargs.get('length', None)}
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

# ===== テスト: _temp_set_velocity =====
def test_temp_set_velocity():
    dev = DummyDevice()
    mc = MotionController(dev)

    orig = mc._temp_set_velocity(ax=1, vel_no=1, velocity=2.5)
    # 読み出し元の値が返却される
    assert orig == {'vel_no': 1, 'start_vel': 5, 'max_vel': 5, 'acc_time': 3, 'acc_type': 2}
    # コマンド実行順序: read_vel_tbl → write_vel_tbl
    assert dev.calls[0][0] == 'read_vel_tbl'
    assert dev.calls[1][0] == 'write_vel_tbl'
    # convert 2.5*10=25 pulse
    assert dev.calls[1][1]['start_vel'] == 25
    assert dev.calls[1][1]['max_vel'] == 25

# ===== テスト: move_relative =====
def test_move_relative_with_restore():
    dev = DummyDevice()
    mc = MotionController(dev)

    result = mc.move_relative(axis=1, length=2.0, velocity=1.5)
    # 結果に元パラメータと変換結果が含まれる
    assert result['length'] == 2.0
    assert result['length_pulse'] == 20
    assert result['velocity_pulse'] == 15
    # コマンド呼び出しシーケンス:
    # read_vel_tbl, write_vel_tbl, move_relative, write_vel_tbl
    names = [c[0] for c in dev.calls]
    assert names == ['read_vel_tbl', 'write_vel_tbl', 'move_relative', 'write_vel_tbl']

# ===== テスト: move_absolute (restore_vel_table=False) =====
def test_move_relative_with_restore():
    dev = DummyDevice()
    mc = MotionController(dev)

    result = mc.move_relative(axis=1, length=2.0, velocity=1.5)
    # length_pulse = 2.0 * 10 = 20 であることを確認
    assert result['length_pulse'] == 20
    # デバイスレスポンスの 'length'（パルス値）が result['length'] に上書きされる
    assert result['length'] == 20
    # ステータスと vel_no も含まれる
    assert result['status'] == 'ok'
    assert result['vel_no'] == 1
    # コマンド呼び出しシーケンス
    names = [c[0] for c in dev.calls]
    assert names == ['read_vel_tbl', 'write_vel_tbl', 'move_relative', 'write_vel_tbl']

# ===== テスト: move_stop =====
def test_move_stop():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.move_stop(axis=1, pat=7)
    assert res == {'stopped': True}
    assert dev.calls == [('move_stop', {'ax_num': 1, 'pat': 7})]

# ===== テスト: home =====
def test_home():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.home(axis=2, velocity=2.0)
    # 速度変換チェック
    assert res['velocity'] == 2.0
    assert res['velocity_pulse'] == 20
    # シーケンス: read_vel_tbl, write_vel_tbl, home, write_vel_tbl
    names = [c[0] for c in dev.calls]
    assert names == ['read_vel_tbl', 'write_vel_tbl', 'home', 'write_vel_tbl']

# ===== テスト: read_position =====
def test_read_position():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_position(axis=1)
    # pos=20→unit=20/10=2.0
    assert res['position'] == 2.0
    assert res['position_pulse'] == 20
    assert res['pos'] == 20

# ===== テスト: read_status =====
def test_read_status():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_status(axis=1)
    assert res == {'status': 0}

# ===== テスト: read_vel_tbl =====
def test_read_vel_tbl():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_vel_tbl(axis=1)
    # start_vel=5→unit=5/10=0.5
    assert res == {
        'vel_no': 1,
        'start_velocity': 0.5,
        'max_velocity': 0.5,
        'acc_time': 3,
        'acc_type': 2,
    }

# ===== テスト: write_vel_tbl =====
def test_write_vel_tbl():
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.write_vel_tbl(axis=1, vel_no=3, start_velocity=1.0, max_velocity=2.0, acc_time=4, acc_type=1)
    # 1.0*10=10, 2.0*10=20
    assert res['start_velocity'] == 1.0
    assert res['start_pulse'] == 10
    assert res['max_velocity'] == 2.0
    assert res['max_pulse'] == 20
