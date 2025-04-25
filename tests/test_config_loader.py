import os
import json
import pytest
from src.kzpy.config_loader import load_config, check_config, DEFAULT_CONFIG_PATHS

# デフォルト設定ファイルパス
ARIES_CONFIG = DEFAULT_CONFIG_PATHS['aries']
CRUX_CONFIG  = DEFAULT_CONFIG_PATHS['crux']
INVALID_PATH = os.path.join(os.path.dirname(__file__), 'nonexistent.json')

@pytest.fixture
def invalid_config1(tmp_path):
    """KeyError を引き起こす構造不正の設定ファイル"""
    invalid_data = {
        "device": "aries",
        "axes_sum": 2,
        # axes が欠落
    }
    invalid_file = tmp_path / "invalid1.json"
    invalid_file.write_text(json.dumps(invalid_data, indent=4), encoding="utf-8")
    return invalid_file

@pytest.fixture
def invalid_config2(tmp_path):
    """TypeError を引き起こす構造不正の設定ファイル"""
    invalid_data = {
        "device": "aries",
        "axes_sum": 2,
        "axes": "not_a_list"  # axes をリストとして定義していない
    }
    invalid_file = tmp_path / "invalid2.json"
    invalid_file.write_text(json.dumps(invalid_data, indent=4), encoding="utf-8")
    return invalid_file


def test_load_config_valid_aries():
    """aries_config.json が正しく読み込めるか"""
    data = load_config(path=ARIES_CONFIG)
    assert isinstance(data, dict)
    assert "device" in data
    assert "axes" in data
    assert data["device"].lower() == "aries"


def test_load_config_valid_crux():
    """crux_config.json が正しく読み込めるか"""
    data = load_config(path=CRUX_CONFIG)
    assert isinstance(data, dict)
    assert "device" in data
    assert "axes" in data
    assert data["device"].lower() == "crux"


def test_load_config_file_not_found():
    """存在しないファイルを読んだときに FileNotFoundError が出るか"""
    with pytest.raises(FileNotFoundError):
        load_config(path=INVALID_PATH)


def test_check_config_valid_aries():
    """aries_config.json が正しくチェックできるか"""
    data = check_config(path=ARIES_CONFIG)
    assert data["device"].lower() == "aries"
    assert len(data["axes"]) == data["axes_sum"]


def test_check_config_valid_crux():
    """crux_config.json が正しくチェックできるか"""
    data = check_config(path=CRUX_CONFIG)
    assert data["device"].lower() == "crux"
    assert len(data["axes"]) == data["axes_sum"]


def test_check_config_invalid_key(invalid_config1):
    """必須キーが不足している場合に KeyError が発生するか"""
    with pytest.raises(KeyError):
        check_config(path=str(invalid_config1))


def test_check_config_invalid_type(invalid_config2):
    """axes がリストでない場合に TypeError が発生するか"""
    with pytest.raises(TypeError):
        check_config(path=str(invalid_config2))
