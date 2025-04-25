"""
src/kzpy/tests/test_serial.py
pytest を使って、_serial モジュールの SerialIO クラスの動作を検証します:
- 通常の send/receive 動作
- ポート未接続時のエラー挙動
"""

import pytest
from unittest.mock import MagicMock, patch
from src.kzpy._serial import SerialIO


@patch("serial.Serial")
def test_serial_send_and_receive(mock_serial_class):
    """
    通常の send → receive の一連の流れをテスト
    """
    mock_serial = MagicMock()
    mock_serial.readline.return_value = b"OK\n"
    mock_serial_class.return_value = mock_serial

    io = SerialIO("COM_TEST", 9600)
    io.open()
    io.send(b"HELLO")
    response = io.receive()

    assert response == b"OK\n"
    mock_serial.write.assert_called_once_with(b"HELLO")
    mock_serial.flush.assert_called_once()
    mock_serial.readline.assert_called_once()

    io.close()
    assert io.ser is None


@patch("serial.Serial")
def test_serial_not_open_raises_error(mock_serial_class):
    """
    open() を呼ばずに send/receive を実行した場合にエラーが出ることをテスト
    """
    io = SerialIO("COM_TEST", 9600)

    with pytest.raises(RuntimeError, match=r"Serial port is not open\. Call open\(\) before sending data\."):
        io.send(b"data")

    with pytest.raises(RuntimeError, match=r"Serial port is not open\. Call open\(\) before receiving data\."):
        io.receive()
