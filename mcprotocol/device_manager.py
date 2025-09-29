"""
Device Manager
==============

デバイス管理ユーティリティ
"""

import re
from typing import Tuple
from .constants import DeviceConstants, iQR_SERIES


class DeviceManager:
    """デバイス管理クラス"""

    @staticmethod
    def parse_device_spec(device_spec: str) -> Tuple[str, int, int]:
        """
        デバイス指定文字列を解析

        Args:
            device_spec: "D100", "D200:5", "M10", "X1A" 等

        Returns:
            (デバイスタイプ, アドレス, 長さ)
        """
        # 長さ指定の確認
        if ":" in device_spec:
            device_part, length_str = device_spec.split(":", 1)
            length = int(length_str)
        else:
            device_part = device_spec
            length = 1

        # H記法の処理（例: XH20）
        if device_part.upper().find("H") > 0:
            h_pos = device_part.upper().find("H")
            device_type = device_part[:h_pos].upper()
            address_str = device_part[h_pos+1:]
            address = int(address_str, 16)
        else:
            # 通常のデバイス指定
            match = re.match(r"^([A-Za-z]+)(.+)$", device_part)
            if not match:
                raise ValueError(f"Invalid device specification: {device_spec}")

            device_type = match.group(1).upper()
            address_str = match.group(2)

            # アドレス解析
            if address_str.startswith("0x") or address_str.startswith("0X"):
                address = int(address_str, 16)
            else:
                # 10進数として解釈、失敗したら16進数として解釈
                try:
                    address = int(address_str, 10)
                except ValueError:
                    # X, Y, B, W, SB, SW, DX, DY, ZRは16進数デバイス
                    hex_devices = {"X", "Y", "B", "W", "SB", "SW", "DX", "DY", "ZR"}
                    if device_type in hex_devices:
                        try:
                            address = int(address_str, 16)
                        except ValueError:
                            raise ValueError(f"Invalid address format: {address_str}")
                    else:
                        raise ValueError(f"Invalid address format: {address_str}")

        return device_type, address, length

    @staticmethod
    def make_device_data(device: str, plctype: str = "iQ-R",
                        commtype: str = "binary") -> bytes:
        """
        デバイスデータ（デバイスコード + デバイス番号）を生成

        Args:
            device: デバイス指定文字列（例: "D1000", "X10"）
            plctype: PLCタイプ
            commtype: 通信タイプ

        Returns:
            デバイスデータのバイト列
        """
        # デバイスタイプとアドレスを抽出
        device_type, address, _ = DeviceManager.parse_device_spec(device)

        device_data = bytes()

        if commtype == "binary":
            # バイナリモード
            devicecode, devicebase = DeviceConstants.get_binary_devicecode(plctype, device_type)

            if plctype == iQR_SERIES:
                # iQ-Rシリーズは4バイトアドレス + 2バイトデバイスコード
                device_data += address.to_bytes(4, "little")
                device_data += devicecode.to_bytes(2, "little")
            else:
                # その他は3バイトアドレス + 1バイトデバイスコード
                device_data += address.to_bytes(3, "little")
                device_data += devicecode.to_bytes(1, "little")

        else:
            # ASCIIモード
            devicecode, devicebase = DeviceConstants.get_ascii_devicecode(plctype, device_type)
            address_str = str(address)

            if plctype == iQR_SERIES:
                device_data += devicecode.encode()
                device_data += address_str.rjust(8, "0").upper().encode()
            else:
                device_data += devicecode.encode()
                device_data += address_str.rjust(6, "0").upper().encode()

        return device_data

    @staticmethod
    def is_bit_device(device_type: str, plctype: str = "iQ-R") -> bool:
        """
        ビットデバイスかどうか判定

        Args:
            device_type: デバイスタイプ
            plctype: PLCタイプ

        Returns:
            ビットデバイスの場合True
        """
        device_type_str = DeviceConstants.get_devicetype(plctype, device_type)
        return device_type_str == DeviceConstants.BIT_DEVICE

    @staticmethod
    def is_word_device(device_type: str, plctype: str = "iQ-R") -> bool:
        """
        ワードデバイスかどうか判定

        Args:
            device_type: デバイスタイプ
            plctype: PLCタイプ

        Returns:
            ワードデバイスの場合True
        """
        device_type_str = DeviceConstants.get_devicetype(plctype, device_type)
        return device_type_str == DeviceConstants.WORD_DEVICE