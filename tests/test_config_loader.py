"""
src/kzpy/tests/test_config_loader.py
test_config_loader.py
pytest を使って、config_loader の動作を検証します。
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError
from src.kzpy.config_loader import (
    load_device_config, check_device_config, DEFAULT_CONFIG_PATHS
)
from src.kzpy._type import DeviceConfig

# テスト用サンプル設定
def sample_config(tmp_path: Path, axes_count: int = 2) -> Path:
    cfg = {
        "device": "TestDev",
        "axes_sum": axes_count,
        "axes": [
            {
                "name": f"a{i}",
                "ax_num": i,
                "units": "um",
                "max_pulse": 100,
                "min_pulse": -100,
                "max_speed_pulse": 50,
                "start_velocity_pulse": 1.0,
                "pulse_per_unit": 0.1,
            }
            for i in range(axes_count)
        ],
        "serial": {"baudrate": 9600, "parity": "N"},
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(cfg), encoding='utf-8')
    return path

# load_device_config のテスト
def test_load_custom_config(tmp_path):
    path = sample_config(tmp_path, axes_count=3)
    cfg = load_device_config(path=str(path))
    assert isinstance(cfg, DeviceConfig)
    assert cfg.axes_sum == 3

# check_device_config の正常系テスト
def test_check_device_config_valid(tmp_path):
    path = sample_config(tmp_path, axes_count=2)
    valid, errors = check_device_config(path=str(path))
    assert valid is True
    assert errors == []

# check_device_config の異常系テスト（スキーマ不一致）
def test_check_device_config_invalid_schema(tmp_path):
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({"foo": "bar"}), encoding='utf-8')
    valid, errors = check_device_config(path=str(bad))
    assert valid is False
    assert any('device' in err for err in errors)

# check_device_config の異常系テスト（ファイル未検出）
def test_check_device_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setitem(DEFAULT_CONFIG_PATHS, 'aries', str(tmp_path / 'no.json'))
    valid, errors = check_device_config(default='aries')
    assert valid is False
    assert any('Configuration file not found' in e for e in errors)

# load_device_config の異常系テスト
def test_load_invalid_schema(tmp_path):
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({"foo": "bar"}), encoding='utf-8')
    with pytest.raises(ValidationError):
        load_device_config(path=str(bad))
