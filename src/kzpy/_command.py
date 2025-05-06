"""
src/kzpy/_command.py
コマンドを生成し、バイト列を送信する機能を提供するクラスです:
- generate_command: コマンドとその引数を元に、バイト列を生成します
- parse_response: シリアル通信のレスポンスをパースし、適切な引数を返します
"""

from typing import Dict, Any

# デフォルトコマンドマップ
default_map: Dict[str, Any] = {
    "move_free": {
        "code": "FRP",
        "args": ["ax_num", "vel_no", "dir"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
    "move_relative": {
        "code": "RPS",
        "args": ["ax_num", "vel_no", "length", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
    "move_absolute": {
        "code": "APS",
        "args": ["ax_num", "vel_no", "length", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
    "move_stop": {
        "code": "STP",
        "args": ["ax_num", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
    "home": {
        "code": "ORG",
        "args": ["ax_num", "vel_no", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
    "identify": {
        "code": "IDN",
        "args": [],
        "res_c": ["dev_name", "dev_var", "minor_ver", "release_ver"],
        "res_e": [],
    },
    "read_position": {
        "code": "RDP",
        "args": ["ax_num"],
        "res_c": ["ax_num", "pos"],
        "res_e": [],
    },
    "read_vel_tbl": {
        "code": "RTB",
        "args": ["ax_num", "vel_no"],
        "res_c": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "acc_type"],
        "res_e": ["ax_num", "error_num"],
    },
    "read_status": {
        "code": "STR",
        "args": ["ax_num"],
        "res_c": ["ax_num", "status", "org_sta", "norg_sta", "ccw_sta", "cw_sta"],
        "res_e": ["ax_num", "error_num"],
    },
    "write_vel_tbl": {
        "code": "WTB",
        "args": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "acc_type"],
        "res_c": ["ax_num"],
        "res_e": ["ax_num", "error_num"],
    },
}

# ARIESバリアント用のコマンドマップ（read_vel_tblやwrite_vel_tblが拡張されている）
aries_command_map: Dict[str, Any] = {
    **default_map,
    "read_axis": {
        "code": "RAX",
        "args": [],
        "res_c": ["ax_num", "control_num"] + [f"island_{i}" for i in range(8)],
        "res_e": ["error_num"],
    },
    "read_vel_tbl": {
        "code": "RTB",
        "args": default_map["read_vel_tbl"]["args"],
        "res_c": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "dec_time", "acc_type", "acc_pulse", "dec_pulse"],
        "res_e": ["ax_num", "error_num"],
    },
    "write_vel_tbl": {
        "code": "WTB",
        "args": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "dec_time", "acc_type"],
        "res_c": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "dec_time", "acc_type", "acc_pulse", "dec_pulse"],
        "res_e": ["ax_num", "error_num"],
    },
    "read_status": {
        "code": "STR",
        "args": ["ax_num"],
        "res_c": ["ax_num", "status", "emg_sta", "org_noorg_sta", "cw_ccw_sta", "soft_sta","limit_sta"],
        "res_e": ["ax_num", "error_num"],
    },
}

class CommandProcessor:
    # 開始・終了文字
    STX = b"\x02"
    CRLF = b"\r\n"

    def __init__(self, variant: str = "default"):
        # コマンドセットのバリアント（"default" または "aries"）
        self.variant = variant
        self.cmd_map = aries_command_map if variant == "aries" else default_map

    def generate_command(self, command_name: str, **kwargs) -> bytes:
        """
        コマンド名と引数から、バイナリ形式の送信用コマンドを生成する
        """
        info = self.cmd_map.get(command_name)
        if not info:
            raise ValueError(f"Invalid command: {command_name}")

        code = info["code"]

        # 定義された引数の中で、実際に渡されたものだけを抽出
        filtered_args = [arg for arg in info.get("args", []) if arg in kwargs]
        args_strs = [str(kwargs[arg]) for arg in filtered_args]

        # コマンドボディを組み立て（スラッシュ区切り）
        body = code
        if args_strs:
            body += args_strs[0]
            for extra in args_strs[1:]:
                body += f"/{extra}"

        # STX + コマンド + CRLF の形式でバイト列化
        raw = CommandProcessor.STX + body.encode('ascii') + CommandProcessor.CRLF
        print(f"[DEBUG] → raw command: {raw!r}")
        return raw

    def parse_response(self, response: str, command: str) -> Dict[str, Any]:
        """
        デバイスからのレスポンスを解析し、フィールド名をキーとした辞書を返す。
        エラー応答の場合は RuntimeError を発生させる。
        """
        info = self.cmd_map.get(command)
        if not info:
            raise ValueError(f"Unknown command: {command}")

        # タブをスペースに変換し、トークンに分割
        tokens = response.strip().replace('\t', ' ').split()
        if not tokens:
            raise ValueError("Empty response")

        prefix = tokens.pop(0)  # "C"（成功）または "E"（エラー）
        code = info["code"]

        # 先頭にコマンドコードが含まれていれば処理
        if tokens:
            first = tokens[0]
            if first == code:
                tokens.pop(0)
            elif first.startswith(code) and first[len(code):].isdigit():
                tokens.pop(0)
                tokens.insert(0, first[len(code):])

        # 成功応答またはエラー応答に応じて期待フィールドを選択
        fields = info["res_c"] if prefix == "C" else info["res_e"]

        # read_vel_tbl のみ default_map のフォールバック対応
        if len(tokens) != len(fields) and command == "read_vel_tbl":
            fallback = default_map.get(command)
            alt_fields = (fallback["res_c"] if prefix == "C" else fallback["res_e"]) if fallback else []
            if len(tokens) == len(alt_fields):
                fields = alt_fields

        if len(tokens) != len(fields):
            kind = "Success" if prefix == "C" else "Error"
            raise ValueError(
                f"{kind} response length mismatch: expected {len(fields)} values, got {len(tokens)}\n"
                f"→ fields: {fields}\n→ tokens: {tokens}"
            )

        result = dict(zip(fields, tokens))

        # エラー応答の場合は例外送出
        if prefix == "E":
            ax_info = f"Axis {result.get('ax_num')}" if "ax_num" in result else "Unknown axis"
            err_info = f"Error {result.get('error_num')}" if "error_num" in result else "Unknown error"
            raise RuntimeError(f"Command '{command}' failed during execution ({ax_info}, {err_info})")

        return result
