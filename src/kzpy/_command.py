"""
src/kzpy/_command.py
コマンドを生成し、バイト列を送信する機能を提供するクラスです:
- generate_command: コマンドとその引数を元に、バイト列を生成します
- parse_response: シリアル通信のレスポンスをパースし、適切な引数を返します
"""

from typing import Dict, Any

# デフォルトコマンドマップ
default_map = {
    "move_free": {
        "code": "FRP",
        "args": ["ax_num", "vel_no", "dir"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    },
    "move_relative": {
        "code": "RPS",
        "args": ["ax_num", "vel_no", "length", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    },
    "move_absolute": {
        "code": "APS",
        "args": ["ax_num", "vel_no", "length", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    },
    "move_stop": {
        "code": "STP",
        "args": ["ax_num", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    },
    "home": {
        "code": "ORG",
        "args": ["ax_num", "vel_no", "pat"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    },
    "identify": {
        "code": "IDN",
        "args": [],
        "res_c": ["dev_name", "dev_var"],
        "res_e": []
    },
    "read_position": {
        "code": "RDP",
        "args": ["ax_num"],
        "res_c": ["ax_num", "pos"],
        "res_e": []
    },
    "read_vel_tbl": {
        "code": "RTB",
        "args": ["ax_num", "vel_no"],
        "res_c": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "acc_type"],
        "res_e": ["error_num"]
    },
    "read_status": {
        "code": "STR",
        "args": ["ax_num"],
        "res_c": ["ax_num", "status", "org_sta", "norg_sta", "ccw_sta", "cw_sta"],
        "res_e": ["error_num"]
    },
    "write_vel_tbl": {
        "code": "WTB",
        "args": ["ax_num", "vel_no", "start_vel", "max_vel", "acc_time", "acc_type"],
        "res_c": ["ax_num"],
        "res_e": ["error_num"]
    }
}

# ARIESバリアント用にデフォルトマップを拡張
aries_command_map = {
    **default_map,
    "read_axis": {
        "code": "RAX",
        "args": [],
        "res_c": ["ax_num", "control_num"] + [f"island_{i}" for i in range(8)],
        "res_e": ["error_num"]
    }
}

class CommandProcessor:
    STX = b"\x02"  # スタートビット
    CRLF = b"\r\n"  # 終了ビット

    def __init__(self, variant: str = "default"):
        # variantに応じたコマンドマップを選択
        if variant == "aries":
            self.cmd_map = aries_command_map
        else:
            self.cmd_map = default_map

    def generate_command(self, command_name: str, **kwargs) -> bytes:
        """
        コマンドを生成して、送信可能なバイト列に整形する。
        """
        cmd_info = self.cmd_map.get(command_name)
        if not cmd_info:
            raise ValueError(f"Invalid command: {command_name}")

        # 必要引数のチェック
        args = []
        for arg in cmd_info.get("args", []):
            if arg not in kwargs:
                raise ValueError(f"Missing required argument: {arg}")
            args.append(str(kwargs[arg]))

        # コマンド文字列の組み立て
        if args:
            # code + first arg, 以降はスラッシュ区切り
            body = cmd_info["code"] + args[0]
            for extra in args[1:]:
                body += f"/{extra}"
        else:
            # 引数なしコマンド
            body = cmd_info["code"]

        # STX + body + CRLF
        return CommandProcessor.STX + body.encode('ascii') + CommandProcessor.CRLF

    def parse_response(self, response: str, command: str) -> Dict[str, Any]:
        """
        コマンドに基づいたレスポンス文字列をパースし、結果を辞書で返す。
        """
        cmd_info = self.cmd_map.get(command)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command}")

        parts = response.split()
        result: Dict[str, Any] = {}

        prefix = parts[0]
        if prefix == "C":  # 正常応答
            expected = cmd_info.get("res_c", [])
            for i in range(1, len(parts), 2):
                key, val = parts[i], parts[i+1]
                if key in expected:
                    result[key] = val
                else:
                    raise ValueError(f"Unexpected key in success response: {key}")
        elif prefix == "E":  # エラー応答
            expected = cmd_info.get("res_e", [])
            if len(parts) < 3:
                raise ValueError("Invalid error response format")
            # error_numは必須
            result["error_num"] = parts[2]
            for i in range(3, len(parts), 2):
                key, val = parts[i], parts[i+1]
                if key in expected:
                    result[key] = val
                else:
                    raise ValueError(f"Unexpected key in error response: {key}")
        else:
            raise ValueError("Invalid response prefix")

        return result
