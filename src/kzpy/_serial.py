"""
src/kzpy/_serial.py
シリアル通信を管理するクラスを提供します:
- open: シリアルポートを開きます
- send: バイト列を送信します
- receive: 応答をバイト列として受け取ります
- send_and_receive: コマンドを送信し、応答を一度に取得します
- close: シリアルポートを明示的に閉じます
"""
import serial
import time
from typing import Optional


class SerialIO:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 0.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def open(self):
        """
        シリアルポートを開く
        """
        if self.ser is None or not self.ser.is_open:
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

    def send(self, data: bytes) -> None:
        """
        バイト列を送信する
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open. Call open() before sending data.")
        self.ser.write(data)
        self.ser.flush()

    def receive(self) -> bytes:
        """
        応答をバイト列で受け取る
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open. Call open() before receiving data.")
        time.sleep(0.1)
        return self.ser.readline()

    def send_and_receive(self, data: bytes) -> bytes:
        """
        送信して、応答をバイト列で受け取る
        """
        self.send(data)
        return self.receive()

    def close(self):
        """
        シリアルポートを閉じる
        """
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
