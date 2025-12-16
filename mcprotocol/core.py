"""
MC Protocol Core Module
=======================

MCプロトコル通信の基本機能実装
"""

import socket
import struct
import re
from typing import Optional, Tuple, List, Union


def twos_complement(val: int, mode: str = "short") -> int:
    """2の補数を計算"""
    bit_sizes = {"byte": 8, "short": 16, "long": 32}

    if mode not in bit_sizes:
        raise ValueError(f"Invalid mode: {mode}")

    bit_size = bit_sizes[mode]
    if (val & (1 << (bit_size - 1))) != 0:
        val = val - (1 << bit_size)
    return val


def get_device_number(device: str) -> str:
    """
    デバイス番号を抽出
    例: "D1000" → "1000", "X0x1A" → "0x1A"
    """
    match = re.search(r"\d.*", device)
    if match is None:
        raise ValueError(f"Invalid device number: {device}")
    return match.group(0)


class MCProtocolCore:
    """MCプロトコル通信コアクラス"""

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._transport: str = "tcp"
        self._remote_addr: Optional[tuple[str, int]] = None
        self._is_connected = False
        self._sockbufsize = 4096
        self._debug = False

    def set_debug(self, debug: bool = False) -> None:
        """デバッグモード設定"""
        self._debug = debug

    def connect(self, ip: str, port: int, timeout: float = 2.0, transport: str = "tcp") -> None:
        """
        PLC接続

        Args:
            ip: IPアドレス
            port: ポート番号
            timeout: タイムアウト秒数
            transport: 輸送層 ("tcp" または "udp")
        """
        transport = transport.lower()
        if transport not in ("tcp", "udp"):
            raise ValueError(f"Invalid transport '{transport}'. Use 'tcp' or 'udp'.")

        try:
            sock_type = socket.SOCK_DGRAM if transport == "udp" else socket.SOCK_STREAM
            self._sock = socket.socket(socket.AF_INET, sock_type)
            self._sock.settimeout(timeout)
            self._sock.connect((ip, port))
            self._transport = transport
            self._remote_addr = (ip, port)
            self._is_connected = True
        except Exception as e:
            from .errors import ConnectionError
            raise ConnectionError(f"Failed to connect to {ip}:{port} - {e}")

    def close(self) -> None:
        """接続を閉じる"""
        if self._sock:
            self._sock.close()
            self._sock = None
        self._is_connected = False

    def _send(self, data: bytes) -> None:
        """データ送信"""
        if not self._is_connected or not self._sock:
            raise Exception("Socket is not connected. Please use connect method")

        if self._debug:
            print(f"Send: {data.hex()}")

        if self._transport == "udp" and self._remote_addr:
            # UDPはコネクションレスだがconnect済みで宛先を固定
            self._sock.sendto(data, self._remote_addr)
        else:
            self._sock.send(data)

    def _recv(self, size: Optional[int] = None) -> bytes:
        """データ受信"""
        if not self._is_connected or not self._sock:
            raise Exception("Socket is not connected")

        if self._transport == "udp":
            recv_data = self._sock.recvfrom(size or self._sockbufsize)[0]
        else:
            recv_data = self._sock.recv(size or self._sockbufsize)

        if self._debug:
            print(f"Recv: {recv_data.hex()}")

        return recv_data

    def encode_value(self, value: int, mode: str = "short",
                    commtype: str = "binary", signed: bool = False) -> bytes:
        """
        値をバイト列にエンコード

        Args:
            value: エンコードする値
            mode: "byte", "short", "long"
            commtype: "binary" or "ascii"
            signed: 符号付きかどうか

        Returns:
            エンコード済みバイト列
        """
        if commtype == "binary":
            size_map = {"byte": 1, "short": 2, "long": 4}
            if mode not in size_map:
                raise ValueError(f"Invalid mode: {mode}")

            return value.to_bytes(size_map[mode], "little", signed=signed)

        else:  # ascii
            if mode == "byte":
                value = value & 0xff
                return format(value, "x").rjust(2, "0").upper().encode()
            elif mode == "short":
                value = value & 0xffff
                return format(value, "x").rjust(4, "0").upper().encode()
            elif mode == "long":
                value = value & 0xffffffff
                return format(value, "x").rjust(8, "0").upper().encode()
            else:
                raise ValueError(f"Invalid mode: {mode}")

    def decode_value(self, data: bytes, mode: str = "short",
                    commtype: str = "binary", signed: bool = False) -> int:
        """
        バイト列を値にデコード

        Args:
            data: デコードするバイト列
            mode: "byte", "short", "long"
            commtype: "binary" or "ascii"
            signed: 符号付きかどうか

        Returns:
            デコード済み値
        """
        if commtype == "binary":
            return int.from_bytes(data, "little", signed=signed)

        else:  # ascii
            value = int(data.decode(), 16)
            if signed:
                value = twos_complement(value, mode)
            return value

    def __enter__(self):
        """コンテキストマネージャー対応"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了時"""
        self.close()
