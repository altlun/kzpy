"""
src/kzpy/config_loader.py
config/*.json から設定を読み込み、DeviceConfig モデルを返却します。
- path を指定するとそのファイルを使用
- 指定がない場合は default (aries/crux) の内部設定ファイルを使用
"""
import json
import os
from typing import Optional, Tuple, List
from pydantic import ValidationError
from ._type import DeviceConfig

# パッケージ内の config ディレクトリ
PKG_DIR = os.path.dirname(__file__)
CONFIG_DIR = os.path.join(PKG_DIR, "config")

# デバイス別デフォルト設定ファイルパス
DEFAULT_CONFIG_PATHS = {
    key: os.path.join(CONFIG_DIR, f"{key}_config.json")
    for key in ("aries", "crux")
}

def load_device_config(path: Optional[str] = None, default: str = "aries") -> DeviceConfig:
    """
    設定ファイルを DeviceConfig として読み込んで返す
    :param path: 明示的なファイルパス
    :param default: 使用する内部デフォルト設定 ('aries' or 'crux')
    :raises FileNotFoundError: ファイルが存在しない
    :raises ValueError: default が不正
    :raises ValidationError: モデルバリデーション失敗
    """
    if path:
        config_path = os.path.abspath(path)
    else:
        key = default.lower()
        if key not in DEFAULT_CONFIG_PATHS:
            raise ValueError(f"default must be one of {list(DEFAULT_CONFIG_PATHS.keys())}: '{default}'")
        config_path = DEFAULT_CONFIG_PATHS[key]

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return DeviceConfig(**data)


def check_device_config(path: Optional[str] = None, default: str = "aries") -> Tuple[bool, List[str]]:
    """
    設定ファイルの妥当性を検証し、結果とエラーリストを返します。
    :return: (True, []) なら正常、(False, errors) なら不正箇所をリストで返却
    """
    errors: List[str] = []
    try:
        load_device_config(path, default)
        return True, []
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err['loc'])
            errors.append(f"{loc}: {err['msg']}")
    except (FileNotFoundError, ValueError) as e:
        errors.append(str(e))
    return False, errors