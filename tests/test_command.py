"""
src/kzpy/tests/test_command.py

CommandProcessor クラスのコマンド生成(generate_command)とレスポンス解析(parse_response)の動作をpytestで検証するテストモジュールです:
- generate_command: 各コマンドが正しいバイト列を出力するか
- parse_response: 成功/エラー応答を正しく解析し、例外を投げるか
"""

import pytest
from src.kzpy._command import CommandProcessor

# --- Default variant: コマンド生成テスト ---

def test_generate_command_move_free():
    # move_free コマンドのデフォルトバリアント生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_free", ax_num=1, vel_no=2, dir=1
    )
    expected = b"\x02FRP1/2/1\r\n"
    assert command_bytes == expected


def test_generate_command_write_vel_tbl_default():
    # write_vel_tbl (default) の生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "write_vel_tbl", ax_num=1, vel_no=2,
        start_vel=10, max_vel=100, acc_time=2, acc_type=3
    )
    expected = b"\x02WTB1/2/10/100/2/3\r\n"
    assert command_bytes == expected


def test_generate_command_read_position():
    # read_position コマンドの生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command("read_position", ax_num=1)
    expected = b"\x02RDP1\r\n"
    assert command_bytes == expected


def test_generate_command_move_relative():
    # move_relative コマンドの生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_relative", ax_num=1, vel_no=2, length=100, pat=1
    )
    expected = b"\x02RPS1/2/100/1\r\n"
    assert command_bytes == expected


def test_generate_command_move_absolute():
    # move_absolute コマンドの生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_absolute", ax_num=1, vel_no=2, length=50, pat=0
    )
    expected = b"\x02APS1/2/50/0\r\n"
    assert command_bytes == expected


def test_generate_command_move_stop():
    # move_stop コマンドの生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command("move_stop", ax_num=1, pat=0)
    expected = b"\x02STP1/0\r\n"
    assert command_bytes == expected


def test_generate_command_home():
    # home コマンドの生成
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "home", ax_num=1, vel_no=3, pat=1
    )
    expected = b"\x02ORG1/3/1\r\n"
    assert command_bytes == expected

# --- Default variant: レスポンス解析（成功）テスト ---

def test_parse_response_success_move_free():
    # 成功応答 'C FRP1' を正しく解析
    cp = CommandProcessor()
    parsed = cp.parse_response("C FRP1", "move_free")
    assert parsed == {"ax_num": "1"}


def test_parse_response_success_read_position():
    # 成功応答 'C RDP 1 123' を解析し、pos フィールドを確認
    cp = CommandProcessor()
    parsed = cp.parse_response("C RDP 1 123", "read_position")
    assert parsed == {"ax_num": "1", "pos": "123"}


def test_parse_response_success_write_vel_tbl():
    # 成功応答 'C WTB1' を解析 (default_map の res_c に合わせる)
    cp = CommandProcessor()
    parsed = cp.parse_response("C WTB1", "write_vel_tbl")
    assert parsed == {"ax_num": "1"}

# --- Default variant: レスポンス解析（エラー）テスト ---

def test_parse_response_error_move_relative():
    # エラー応答 'E RPS 1 3' で RuntimeError を送出し、メッセージに軸番号とエラー番号が含まれる
    cp = CommandProcessor()
    with pytest.raises(RuntimeError) as excinfo:
        cp.parse_response("E RPS 1 3", "move_relative")
    msg = str(excinfo.value)
    assert "Axis 1" in msg and "Error 3" in msg

# --- ARIES variant: コマンド生成テスト ---

def test_generate_command_read_axis_aries():
    # ARIESバリアントで read_axis コマンド生成
    cp = CommandProcessor(variant="aries")
    command_bytes = cp.generate_command("read_axis")
    expected = b"\x02RAX\r\n"
    assert command_bytes == expected


def test_generate_command_read_vel_tbl_aries():
    # ARIESバリアントで拡張された read_vel_tbl 生成
    cp = CommandProcessor(variant="aries")
    command_bytes = cp.generate_command(
        "read_vel_tbl", ax_num=0, vel_no=1
    )
    expected = b"\x02RTB0/1\r\n"
    assert command_bytes == expected


def test_generate_command_write_vel_tbl_aries():
    # ARIESバリアントで拡張された write_vel_tbl 生成
    cp = CommandProcessor(variant="aries")
    command_bytes = cp.generate_command(
        "write_vel_tbl", ax_num=2, vel_no=3, start_vel=20,
        max_vel=200, acc_time=4, dec_time=5, acc_type=1
    )
    expected = b"\x02WTB2/3/20/200/4/5/1\r\n"
    assert command_bytes == expected

# --- ARIES variant: レスポンス解析テスト ---

def test_parse_response_success_read_axis_aries():
    # 成功応答 for read_axis を解析（8個のislandフィールドも含む）
    cp = CommandProcessor(variant="aries")
    tokens = [str(i) for i in range(10)]  # ax_num, control_num, island_0...island_7
    resp = "C RAX " + " ".join(tokens)
    parsed = cp.parse_response(resp, "read_axis")
    expected_keys = ["ax_num", "control_num"] + [f"island_{i}" for i in range(8)]
    assert all(k in parsed for k in expected_keys)


def test_parse_response_error_read_vel_tbl_aries():
    # ARIESバリアントでエラー応答を解析し、エラー例外を送出する
    cp = CommandProcessor(variant="aries")
    with pytest.raises(RuntimeError) as excinfo:
        cp.parse_response("E RTB 4 99", "read_vel_tbl")
    msg = str(excinfo.value)
    assert "Axis 4" in msg and "Error 99" in msg
