# lib/config_loader.py
import json
import os
from typing import Any, Dict

# プロジェクトルートからの config ディレクトリ
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# デバイス別デフォルト設定ファイルパス
DEFAULT_CONFIG_PATHS = {
    "aries": os.path.join(CONFIG_DIR, "aries_config.json"),
    "crux":  os.path.join(CONFIG_DIR, "crux_config.json"),
}

# JSON の必須キー定義
REQUIRED_TOP_KEYS = ["device", "axes_sum", "axes"]
REQUIRED_AXIS_KEYS = [
    "name",
    "ax_num",
    "units",
    "min_pulse",
    "max_pulse",
    "start_velocity_pulse",
    "max_speed_pulse",
    "pulse_per_unit",
]


def load_config(path: str = None, default: str = "aries") -> Dict[str, Any]:
    """
    設定ファイルを読み込んで辞書を返却する。
    path が None なら internal default を使う。
    """
    if path:
        config_path = os.path.abspath(path)
    else:
        key = default.lower()
        if key not in DEFAULT_CONFIG_PATHS:
            raise ValueError(f"default は {list(DEFAULT_CONFIG_PATHS.keys())} のいずれか: {default}")
        config_path = DEFAULT_CONFIG_PATHS[key]

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_config(path: str = None, default: str = "aries") -> Dict[str, Any]:
    """
    load_config で読んだ内容を検証し、問題なければ返却。
    """
    data = load_config(path, default)

    # トップレベルキー検証
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            raise KeyError(f"必須キー '{key}' がありません")

    # axes 検証
    axes = data["axes"]
    if not isinstance(axes, list):
        raise TypeError("'axes' はリストである必要があります")
    if data["axes_sum"] != len(axes):
        raise ValueError(
            f"axes_sum ({data['axes_sum']}) != axes の要素数 ({len(axes)})"
        )

    # 各軸のキー検証
    for idx, axis in enumerate(axes):
        if not isinstance(axis, dict):
            raise TypeError(f"axes[{idx}] が辞書ではありません: {axis}")
        for k in REQUIRED_AXIS_KEYS:
            if k not in axis:
                raise KeyError(f"axes[{idx}] の必須キー '{k}' がありません")

    return data


if __name__ == "__main__":
    # 動作確認
    for device in ["aries", "crux"]:
        try:
            cfg = check_config(default=device)
            print(f"{device} OK:", cfg)
        except Exception as e:
            print(f"{device} エラー:", e)
