"""
src/kzpy/_command.py の `CommandProcessor` クラスのメソッドのテスト:
- `generate_command`: コマンドをバイト列に変換できるか
- `parse_response`: 正常応答とエラーレスポンスのパースができるか
"""
import pytest
from src.kzpy._command import CommandProcessor

# コマンドの生成テスト
def test_generate_command():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_free", ax_num=1, vel_no=2, dir=1
    )
    expected_bytes = b"\x02FRP1/2/1\r\n"
    assert command_bytes == expected_bytes

# 正常レスポンスをパースするテスト
def test_parse_response_success():
    cp = CommandProcessor()
    response = "C ax_num 1"
    parsed = cp.parse_response(response, "move_free")
    assert parsed == {"ax_num": "1"}

# エラーレスポンスをパースするテスト
def test_parse_response_error():
    cp = CommandProcessor()
    response = "E error_num 123"
    parsed = cp.parse_response(response, "move_free")
    assert parsed == {"error_num": "123"}

# 無効なレスポンスが来た場合、ValueErrorが発生するテスト
def test_parse_response_invalid():
    cp = CommandProcessor()
    response = "X some_value"
    with pytest.raises(ValueError):
        cp.parse_response(response, "move_free")

# write_vel_tbl コマンドの生成テスト
def test_write_vel_tbl():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "write_vel_tbl", ax_num=1, vel_no=2, start_vel=10, max_vel=100, acc_time=2, acc_type=3
    )
    expected_bytes = b"\x02WTB1/2/10/100/2/3\r\n"
    assert command_bytes == expected_bytes

# read_position コマンドの生成テスト
def test_read_position():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "read_position", ax_num=1
    )
    expected_bytes = b"\x02RDP1\r\n"
    assert command_bytes == expected_bytes

# read_status コマンドのレスポンス解析テスト
def test_parse_read_status_success():
    cp = CommandProcessor()
    response = "C ax_num 1 status 0 org_sta 1 norg_sta 0 ccw_sta 0 cw_sta 0"
    parsed = cp.parse_response(response, "read_status")
    assert parsed == {
        "ax_num": "1",
        "status": "0",
        "org_sta": "1",
        "norg_sta": "0",
        "ccw_sta": "0",
        "cw_sta": "0"
    }

# read_vel_tbl コマンドのレスポンス解析テスト
def test_parse_read_vel_tbl_success():
    cp = CommandProcessor()
    response = "C ax_num 1 vel_no 2 start_vel 10 max_vel 100 acc_time 2 acc_type 3"
    parsed = cp.parse_response(response, "read_vel_tbl")
    assert parsed == {
        "ax_num": "1",
        "vel_no": "2",
        "start_vel": "10",
        "max_vel": "100",
        "acc_time": "2",
        "acc_type": "3"
    }

# move_relative コマンドの生成テスト
def test_move_relative():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_relative", ax_num=1, vel_no=2, length=100, pat=1
    )
    expected_bytes = b"\x02RPS1/2/100/1\r\n"
    assert command_bytes == expected_bytes

# move_absolute コマンドの生成テスト
def test_move_absolute():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_absolute", ax_num=1, vel_no=2, length=50, pat=0
    )
    expected_bytes = b"\x02APS1/2/50/0\r\n"
    assert command_bytes == expected_bytes

# move_stop コマンドの生成テスト
def test_move_stop():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "move_stop", ax_num=1, pat=0
    )
    expected_bytes = b"\x02STP1/0\r\n"
    assert command_bytes == expected_bytes

# home コマンドの生成テスト
def test_home():
    cp = CommandProcessor()
    command_bytes = cp.generate_command(
        "home", ax_num=1, vel_no=3, pat=1
    )
    expected_bytes = b"\x02ORG1/3/1\r\n"
    assert command_bytes == expected_bytes

# identify コマンドのレスポンス解析テスト
def test_identify_response():
    cp = CommandProcessor()
    response = "C dev_name MyDevice dev_var 1.0"
    parsed = cp.parse_response(response, "identify")
    assert parsed == {"dev_name": "MyDevice", "dev_var": "1.0"}


