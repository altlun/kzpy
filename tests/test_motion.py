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

# ===== pytest fixture: patch validation functions =====
@pytest.fixture(autouse=True)
def patch_validators(monkeypatch):
    # テスト用に軸設定と変換関数をパッチする
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
# ===== pytest fixture: skip ensure_idle in tests =====
@pytest.fixture(autouse=True)
def skip_idle(monkeypatch):
    """
    同期版 move_* 系で内部的に呼ばれる ensure_idle を
    テスト中は no-op にして、read_status の余計な呼び出しを防ぐ
    """
    import src.kzpy.motion as mmod
    monkeypatch.setattr(mmod.MotionController, 'ensure_idle', lambda self, axis, poll_interval=0.1: None)
    yield

# ===== Dummy device for testing =====
class DummyDevice:
    def __init__(self):
        self._config = SimpleNamespace()
        self.target_vel_no = 1
        self.restore_vel_table = False
        self._processor = SimpleNamespace(
            variant='default',
            cmd_map={'write_vel_tbl': {'args': ['ax_num', 'vel_no', 'start_vel', 'max_vel', 'acc_time', 'acc_type']}}
        )
        self.calls = []

    def _execute_command(self, name, **kwargs):
        # コマンド実行履歴を記録し、模擬レスポンスを返す
        self.calls.append((name, kwargs.copy()))
        if name == 'read_vel_tbl':
            return {'vel_no': kwargs['vel_no'], 'start_vel': 5, 'max_vel': 5, 'acc_time': 3, 'acc_type': 2}
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

# ===== Tests for MotionController =====

def test_write_vel_tbl_int_args():
    # 速度テーブル書き込みが適切に整数変換されるかを確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.write_vel_tbl(axis=1, vel_no=3, max_velocity=2.0, acc_time=4, acc_type=1)

    assert res['start_pulse'] == 16
    assert res['max_pulse'] == 20
    assert res['acc_time'] == 4
    assert res['acc_type'] == 1
    assert [c[0] for c in dev.calls] == ['read_vel_tbl', 'write_vel_tbl']

    # 引数がすべて整数であることを確認
    _, kwargs = dev.calls[1]
    for v in kwargs.values():
        assert isinstance(v, int)

def test_temp_set_velocity_int_args():
    # 一時的に速度を変更し、書き込みが整数で行われるかを確認
    dev = DummyDevice()
    mc = MotionController(dev)

    orig = mc._temp_set_velocity(ax=1, vel_no=1, velocity=2.5)

    assert orig['vel_no'] == 1
    assert orig['start_vel'] == 5
    assert orig['max_vel'] == 5
    assert orig['acc_time'] == 3
    assert orig['acc_type'] == 2

    proc = mc._get_processor()
    expected_variant = getattr(proc, 'variant', None)
    assert orig['_variant'] == expected_variant
    assert [call[0] for call in dev.calls] == ['read_vel_tbl', 'write_vel_tbl']

    _, write_kwargs = dev.calls[1]
    for v in write_kwargs.values():
        assert isinstance(v, int)

def test_move_relative_sequence_and_types():
    # 相対移動のパルス変換と引数型チェック
    dev = DummyDevice()
    mc = MotionController(dev)

    result = mc.move_relative(axis=1, length=2.0, velocity=1.5)
    assert result['length_pulse'] == 20
    assert result['velocity_pulse'] == 15
    assert result['length'] == 20
    assert result['status'] == 'ok'
    assert result['vel_no'] == 1
    assert [c[0] for c in dev.calls] == ['read_vel_tbl', 'write_vel_tbl', 'move_relative']
    for _, kwargs in dev.calls:
        for v in kwargs.values():
            assert isinstance(v, int)

def test_move_absolute_sequence_and_types():
    # 絶対位置移動と各パラメータの変換を確認
    dev = DummyDevice()
    mc = MotionController(dev)

    result = mc.move_absolute(axis=2, position=3.5, velocity=2.0)
    assert result['position_pulse'] == 35
    assert result['velocity_pulse'] == 20
    assert result['position'] == 35
    assert result['status'] == 'ok'
    assert [c[0] for c in dev.calls] == ['read_vel_tbl', 'write_vel_tbl', 'move_absolute']
    for _, kwargs in dev.calls:
        for v in kwargs.values():
            assert isinstance(v, int)

def test_move_stop_int_args():
    # モータ停止処理で ax_num, pat が整数で渡されるか確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.move_stop(axis=1, pat=7)
    assert res == {'stopped': True}
    name, kwargs = dev.calls[0]
    assert name == 'move_stop'
    assert kwargs == {'ax_num': 1, 'pat': 7}

def test_home_sequence_and_ints():
    # 原点復帰処理と速度設定が適切に行われるか確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.home(axis=2, velocity=2.0)
    assert res['velocity_pulse'] == 20
    assert res['velocity'] == 2.0
    assert [c[0] for c in dev.calls] == ['read_vel_tbl', 'write_vel_tbl', 'home']
    for _, kwargs in dev.calls:
        for v in kwargs.values():
            assert isinstance(v, int)

def test_read_position_and_types():
    # 現在位置取得と単位変換の正当性を確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_position(axis=1)
    assert res['position'] == 2.0
    assert res['position_pulse'] == 20
    assert res['pos'] == 20
    name, kwargs = dev.calls[0]
    assert name == 'read_position'
    assert isinstance(kwargs['ax_num'], int)

def test_read_status_int():
    # ステータス取得と整数引数の確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_status(axis=1)
    assert res == {'status': 0}
    name, kwargs = dev.calls[0]
    assert name == 'read_status'
    assert isinstance(kwargs['ax_num'], int)

def test_read_vel_tbl_conversion():
    # 速度テーブル読み込みと変換値の確認
    dev = DummyDevice()
    mc = MotionController(dev)

    res = mc.read_vel_tbl(axis=1)
    assert res == {
        'vel_no': 1,
        'start_velocity': 0.5,
        'max_velocity': 0.5,
        'acc_time': 3,
        'acc_type': 2,
    }
    name, kwargs = dev.calls[0]
    assert name == 'read_vel_tbl'
    assert isinstance(kwargs['ax_num'], int) and isinstance(kwargs['vel_no'], int)
