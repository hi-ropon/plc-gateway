"""
MC Protocol Constants
====================

MCプロトコルで使用する定数定義
"""

from typing import Tuple, Optional


# PLC定義
Q_SERIES = "Q"
L_SERIES = "L"
QnA_SERIES = "QnA"
iQL_SERIES = "iQ-L"
iQR_SERIES = "iQ-R"

# 通信タイプ
COMMTYPE_BINARY = "binary"
COMMTYPE_ASCII = "ascii"


class DeviceConstants:
    """MCプロトコルデバイス定数クラス"""

    # 全シリーズ共通デバイス
    SM_DEVICE = 0x91
    SD_DEVICE = 0xA9
    X_DEVICE = 0x9C
    Y_DEVICE = 0x9D
    M_DEVICE = 0x90
    L_DEVICE = 0x92
    F_DEVICE = 0x93
    V_DEVICE = 0x94
    B_DEVICE = 0xA0
    D_DEVICE = 0xA8
    W_DEVICE = 0xB4
    TS_DEVICE = 0xC1
    TC_DEVICE = 0xC0
    TN_DEVICE = 0xC2
    SS_DEVICE = 0xC7
    SC_DEVICE = 0xC6
    SN_DEVICE = 0xC8
    CS_DEVICE = 0xC4
    CC_DEVICE = 0xC3
    CN_DEVICE = 0xC5
    SB_DEVICE = 0xA1
    SW_DEVICE = 0xB5
    DX_DEVICE = 0xA2
    DY_DEVICE = 0xA3
    R_DEVICE = 0xAF
    ZR_DEVICE = 0xB0

    # iQ-Rシリーズ専用デバイス
    LTS_DEVICE = 0x51
    LTC_DEVICE = 0x50
    LTN_DEVICE = 0x52
    LSTS_DEVICE = 0x59
    LSTC_DEVICE = 0x58
    LSTN_DEVICE = 0x5A
    LCS_DEVICE = 0x55
    LCC_DEVICE = 0x54
    LCN_DEVICE = 0x56
    LZ_DEVICE = 0x62
    RD_DEVICE = 0x2C

    # デバイスタイプ
    BIT_DEVICE = "bit"
    WORD_DEVICE = "word"
    DWORD_DEVICE = "dword"

    @staticmethod
    def get_binary_devicecode(plctype: str, devicename: str) -> Tuple[int, int]:
        """
        バイナリモード用デバイスコード取得

        Args:
            plctype: PLCタイプ ("Q", "L", "QnA", "iQ-L", "iQ-R")
            devicename: デバイス名 ("D", "X", "Y"等)

        Returns:
            (デバイスコード, 基数)
        """
        device_map = {
            "SM": (DeviceConstants.SM_DEVICE, 10),
            "SD": (DeviceConstants.SD_DEVICE, 10),
            "X": (DeviceConstants.X_DEVICE, 16),
            "Y": (DeviceConstants.Y_DEVICE, 16),
            "M": (DeviceConstants.M_DEVICE, 10),
            "L": (DeviceConstants.L_DEVICE, 10),
            "F": (DeviceConstants.F_DEVICE, 10),
            "V": (DeviceConstants.V_DEVICE, 10),
            "B": (DeviceConstants.B_DEVICE, 16),
            "D": (DeviceConstants.D_DEVICE, 10),
            "W": (DeviceConstants.W_DEVICE, 16),
            "TS": (DeviceConstants.TS_DEVICE, 10),
            "TC": (DeviceConstants.TC_DEVICE, 10),
            "TN": (DeviceConstants.TN_DEVICE, 10),
            "STS": (DeviceConstants.SS_DEVICE, 10),
            "STC": (DeviceConstants.SC_DEVICE, 10),
            "STN": (DeviceConstants.SN_DEVICE, 10),
            "CS": (DeviceConstants.CS_DEVICE, 10),
            "CC": (DeviceConstants.CC_DEVICE, 10),
            "CN": (DeviceConstants.CN_DEVICE, 10),
            "SB": (DeviceConstants.SB_DEVICE, 16),
            "SW": (DeviceConstants.SW_DEVICE, 16),
            "DX": (DeviceConstants.DX_DEVICE, 16),
            "DY": (DeviceConstants.DY_DEVICE, 16),
            "R": (DeviceConstants.R_DEVICE, 10),
            "ZR": (DeviceConstants.ZR_DEVICE, 16),
        }

        # iQ-Rシリーズ専用デバイス
        if plctype == iQR_SERIES:
            iqr_map = {
                "LTS": (DeviceConstants.LTS_DEVICE, 10),
                "LTC": (DeviceConstants.LTC_DEVICE, 10),
                "LTN": (DeviceConstants.LTN_DEVICE, 10),
                "LSTS": (DeviceConstants.LSTS_DEVICE, 10),
                "LSTN": (DeviceConstants.LSTN_DEVICE, 10),
                "LCS": (DeviceConstants.LCS_DEVICE, 10),
                "LCC": (DeviceConstants.LCC_DEVICE, 10),
                "LCN": (DeviceConstants.LCN_DEVICE, 10),
                "LZ": (DeviceConstants.LZ_DEVICE, 10),
                "RD": (DeviceConstants.RD_DEVICE, 10),
            }
            device_map.update(iqr_map)

        if devicename in device_map:
            return device_map[devicename]
        else:
            from .errors import DeviceCodeError
            raise DeviceCodeError(plctype, devicename)

    @staticmethod
    def get_ascii_devicecode(plctype: str, devicename: str) -> Tuple[str, int]:
        """
        ASCIIモード用デバイスコード取得

        Args:
            plctype: PLCタイプ
            devicename: デバイス名

        Returns:
            (デバイスコード文字列, 基数)
        """
        padding = 4 if plctype == iQR_SERIES else 2

        device_map = {
            "SM": (devicename.ljust(padding, "*"), 10),
            "SD": (devicename.ljust(padding, "*"), 10),
            "X": (devicename.ljust(padding, "*"), 16),
            "Y": (devicename.ljust(padding, "*"), 16),
            "M": (devicename.ljust(padding, "*"), 10),
            "L": (devicename.ljust(padding, "*"), 10),
            "F": (devicename.ljust(padding, "*"), 10),
            "V": (devicename.ljust(padding, "*"), 10),
            "B": (devicename.ljust(padding, "*"), 16),
            "D": (devicename.ljust(padding, "*"), 10),
            "W": (devicename.ljust(padding, "*"), 16),
            "TS": (devicename.ljust(padding, "*"), 10),
            "TC": (devicename.ljust(padding, "*"), 10),
            "TN": (devicename.ljust(padding, "*"), 10),
            "CS": (devicename.ljust(padding, "*"), 10),
            "CC": (devicename.ljust(padding, "*"), 10),
            "CN": (devicename.ljust(padding, "*"), 10),
            "SB": (devicename.ljust(padding, "*"), 16),
            "SW": (devicename.ljust(padding, "*"), 16),
            "DX": (devicename.ljust(padding, "*"), 16),
            "DY": (devicename.ljust(padding, "*"), 16),
            "R": (devicename.ljust(padding, "*"), 10),
            "ZR": (devicename.ljust(padding, "*"), 16),
        }

        # STSなどの特殊処理
        if devicename == "STS":
            return ("STS" if plctype == iQR_SERIES else "SS").ljust(padding, "*"), 10
        elif devicename == "STC":
            return ("STC" if plctype == iQR_SERIES else "SC").ljust(padding, "*"), 10
        elif devicename == "STN":
            return ("STN" if plctype == iQR_SERIES else "SN").ljust(padding, "*"), 10

        # iQ-Rシリーズ専用
        if plctype == iQR_SERIES:
            iqr_map = {
                "LTS": (devicename.ljust(padding, "*"), 10),
                "LTC": (devicename.ljust(padding, "*"), 10),
                "LTN": (devicename.ljust(padding, "*"), 10),
                "LSTS": (devicename.ljust(padding, "*"), 10),
                "LSTN": (devicename.ljust(padding, "*"), 10),
                "LCS": (devicename.ljust(padding, "*"), 10),
                "LCC": (devicename.ljust(padding, "*"), 10),
                "LCN": (devicename.ljust(padding, "*"), 10),
                "LZ": (devicename.ljust(padding, "*"), 10),
                "RD": (devicename.ljust(padding, "*"), 10),
            }
            device_map.update(iqr_map)

        if devicename in device_map:
            return device_map[devicename]
        else:
            from .errors import DeviceCodeError
            raise DeviceCodeError(plctype, devicename)

    @staticmethod
    def get_devicetype(plctype: str, devicename: str) -> str:
        """
        デバイスタイプ取得 ("bit" or "word")

        Args:
            plctype: PLCタイプ
            devicename: デバイス名

        Returns:
            "bit", "word", または "dword"
        """
        bit_devices = {"SM", "X", "Y", "M", "L", "F", "V", "B", "TS", "TC",
                      "STS", "STC", "CS", "CC", "SB", "DX", "DY"}
        word_devices = {"SD", "D", "W", "TN", "STN", "CN", "SW", "R", "ZR", "RD"}
        dword_devices = {"LSTN", "LCN", "LZ"}

        if plctype == iQR_SERIES:
            bit_devices.update({"LTS", "LTC", "LTN", "LSTS", "LCS", "LCC"})
            if devicename in dword_devices:
                return DeviceConstants.DWORD_DEVICE

        if devicename in bit_devices:
            return DeviceConstants.BIT_DEVICE
        elif devicename in word_devices:
            return DeviceConstants.WORD_DEVICE
        else:
            from .errors import DeviceCodeError
            raise DeviceCodeError(plctype, devicename)