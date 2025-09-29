"""
MC Protocol Error Handling
=========================

MCプロトコル通信のエラー処理
"""


class MCProtocolError(Exception):
    """MCプロトコル基本エラークラス"""

    def __init__(self, errorcode: int):
        self.errorcode = errorcode
        self.errorcode_hex = "0x" + format(errorcode, "x").rjust(4, "0").upper()
        super().__init__(f"MC protocol error: {self.errorcode_hex}")


class DeviceCodeError(Exception):
    """デバイスコードエラー（存在しないデバイス）"""

    def __init__(self, plctype: str, devicename: str):
        self.plctype = plctype
        self.devicename = devicename
        message = (
            f"Device '{devicename}' is not supported on {plctype} series PLC.\n"
            "For hexadecimal devices (X, Y, B, W, SB, SW, DX, DY, ZR) with alphabetic addresses,\n"
            "insert '0' between device name and address (e.g., XFFF → X0FFF)"
        )
        super().__init__(message)


class CommTypeError(Exception):
    """通信タイプエラー"""

    def __init__(self):
        super().__init__('Communication type must be "binary" or "ascii"')


class PLCTypeError(Exception):
    """PLCタイプエラー"""

    def __init__(self):
        super().__init__('PLC type must be "Q", "L", "QnA", "iQ-L", or "iQ-R"')


class UnsupportedCommandError(Exception):
    """サポートされていないコマンド"""

    def __init__(self):
        super().__init__(
            "This command is not supported by the connected module. "
            "If connecting to CPU module, please use E71 module."
        )


class ConnectionError(Exception):
    """PLC接続エラー"""

    def __init__(self, message: str):
        super().__init__(f"PLC connection error: {message}")


class TimeoutError(Exception):
    """通信タイムアウトエラー"""

    def __init__(self, timeout_sec: float):
        super().__init__(f"Communication timeout after {timeout_sec} seconds")


def check_mcprotocol_error(status: int) -> None:
    """
    MCプロトコルコマンドエラーチェック

    Args:
        status: 応答ステータスコード

    Raises:
        各種MCプロトコルエラー
    """
    if status == 0:
        return

    # よく発生するエラーコード
    error_messages = {
        0xC059: UnsupportedCommandError,
        0xC050: ("PLC内部エラー", MCProtocolError),
        0xC051: ("PLCモードエラー（RUNモードでない）", MCProtocolError),
        0xC052: ("デバイスポイント不正", MCProtocolError),
        0xC053: ("デバイス範囲外", MCProtocolError),
        0xC054: ("デバイス書き込み不可", MCProtocolError),
        0xC055: ("プログラム実行中", MCProtocolError),
        0xC056: ("命令異常", MCProtocolError),
        0xC058: ("パラメータ異常", MCProtocolError),
        0xC05C: ("要求データ異常", MCProtocolError),
        0xC05F: ("要求内容異常", MCProtocolError),
        0xC060: ("要求データ長異常", MCProtocolError),
        0xC061: ("モニタ登録数オーバー", MCProtocolError),
        0xC0B5: ("CPU処理異常", MCProtocolError),
    }

    if status == 0xC059:
        raise UnsupportedCommandError()
    elif status in error_messages:
        msg, error_class = error_messages[status]
        error = error_class(status)
        error.message = msg
        raise error
    else:
        raise MCProtocolError(status)