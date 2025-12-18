"""
MC Protocol Type 3E Implementation
==================================

MCプロトコル3Eタイプ通信実装
"""

from typing import List, Optional, Tuple
from .core import MCProtocolCore, get_device_number
from .device_manager import DeviceManager
from .constants import *
from .errors import *


class Type3E(MCProtocolCore):
    """MCプロトコル3E通信クラス"""

    def __init__(self, plctype: str = "iQ-R"):
        """
        コンストラクタ

        Args:
            plctype: PLCタイプ ("Q", "L", "QnA", "iQ-L", "iQ-R")
        """
        super().__init__()
        self._set_plctype(plctype)

        # デフォルト設定
        self.commtype = COMMTYPE_BINARY
        self.subheader = 0x5000
        self.network = 0
        self.pc = 0xFF
        self.dest_moduleio = 0x3FF
        self.dest_modulesta = 0x0
        self.timer = 4  # 250msec * 4 = 1秒
        self.soc_timeout = 2  # ソケットタイムアウト
        self._wordsize = 2  # binaryの場合2, asciiの場合4

    def _set_plctype(self, plctype: str) -> None:
        """PLCタイプ設定"""
        valid_types = {
            "Q": Q_SERIES,
            "L": L_SERIES,
            "QnA": QnA_SERIES,
            "iQ-L": iQL_SERIES,
            "iQ-R": iQR_SERIES
        }

        if plctype not in valid_types:
            raise PLCTypeError()

        self.plctype = valid_types[plctype]

    def _set_commtype(self, commtype: str) -> None:
        """通信タイプ設定"""
        if commtype == "binary":
            self.commtype = COMMTYPE_BINARY
            self._wordsize = 2
        elif commtype == "ascii":
            self.commtype = COMMTYPE_ASCII
            self._wordsize = 4
        else:
            raise CommTypeError()

    def setaccessopt(self, commtype: Optional[str] = None,
                    network: Optional[int] = None,
                    pc: Optional[int] = None,
                    dest_moduleio: Optional[int] = None,
                    dest_modulesta: Optional[int] = None,
                    timer_sec: Optional[int] = None) -> None:
        """
        アクセスオプション設定

        Args:
            commtype: 通信タイプ ("binary" or "ascii")
            network: ネットワーク番号 (0-255)
            pc: PC番号 (0-255)
            dest_moduleio: 接続先モジュールI/O番号
            dest_modulesta: 接続先モジュール局番
            timer_sec: タイムアウト秒数
        """
        if commtype:
            self._set_commtype(commtype)
        if network is not None:
            if 0 <= network <= 255:
                self.network = network
            else:
                raise ValueError("network must be 0 <= network <= 255")
        if pc is not None:
            if 0 <= pc <= 255:
                self.pc = pc
            else:
                raise ValueError("pc must be 0 <= pc <= 255")
        if dest_moduleio is not None:
            if 0 <= dest_moduleio <= 65535:
                self.dest_moduleio = dest_moduleio
            else:
                raise ValueError("dest_moduleio must be 0 <= dest_moduleio <= 65535")
        if dest_modulesta is not None:
            if 0 <= dest_modulesta <= 255:
                self.dest_modulesta = dest_modulesta
            else:
                raise ValueError("dest_modulesta must be 0 <= dest_modulesta <= 255")
        if timer_sec is not None:
            timer_250msec = 4 * timer_sec
            if 0 <= timer_250msec <= 65535:
                self.timer = timer_250msec
                self.soc_timeout = timer_sec + 1
            else:
                raise ValueError("timer_sec must be 0 <= timer_sec <= 16383")

    def _make_senddata(self, request_data: bytes) -> bytes:
        """送信データ作成"""
        mc_data = bytes()

        # サブヘッダー（ビッグエンディアン）
        if self.commtype == COMMTYPE_BINARY:
            mc_data += self.subheader.to_bytes(2, "big")
        else:
            mc_data += format(self.subheader, "x").rjust(4, "0").upper().encode()

        # ヘッダー情報
        mc_data += self.encode_value(self.network, "byte", self.commtype)
        mc_data += self.encode_value(self.pc, "byte", self.commtype)
        mc_data += self.encode_value(self.dest_moduleio, "short", self.commtype)
        mc_data += self.encode_value(self.dest_modulesta, "byte", self.commtype)

        # データ長（タイマー分を加算）
        data_length = self._wordsize + len(request_data)
        mc_data += self.encode_value(data_length, "short", self.commtype)

        # タイマー
        mc_data += self.encode_value(self.timer, "short", self.commtype)

        # リクエストデータ
        mc_data += request_data

        return mc_data

    def _make_commanddata(self, command: int, subcommand: int) -> bytes:
        """コマンドデータ作成"""
        command_data = bytes()
        command_data += self.encode_value(command, "short", self.commtype)
        command_data += self.encode_value(subcommand, "short", self.commtype)
        return command_data

    def _make_devicedata(self, device: str) -> bytes:
        """デバイスデータ作成"""
        return DeviceManager.make_device_data(device, self.plctype, self.commtype)

    def _get_answerdata_index(self) -> int:
        """応答データ開始インデックス取得"""
        return 11 if self.commtype == COMMTYPE_BINARY else 22

    def _get_answerstatus_index(self) -> int:
        """応答ステータスインデックス取得"""
        return 9 if self.commtype == COMMTYPE_BINARY else 18

    def _check_cmdanswer(self, recv_data: bytes) -> None:
        """コマンド応答チェック"""
        status_index = self._get_answerstatus_index()
        status = self.decode_value(
            recv_data[status_index:status_index+self._wordsize],
            "short", self.commtype
        )
        check_mcprotocol_error(status)

    def batchread_wordunits(self, headdevice: str, readsize: int) -> List[int]:
        """
        ワード単位バッチ読み取り

        Args:
            headdevice: 先頭デバイス（例: "D1000"）
            readsize: 読み取りデバイス数

        Returns:
            ワード値リスト
        """
        command = 0x0401
        subcommand = 0x0002 if self.plctype == iQR_SERIES else 0x0000

        # リクエストデータ作成
        request_data = bytes()
        request_data += self._make_commanddata(command, subcommand)
        request_data += self._make_devicedata(headdevice)
        request_data += self.encode_value(readsize, "short", self.commtype)

        # 送信データ作成・送信
        send_data = self._make_senddata(request_data)
        self._send(send_data)

        # 受信・チェック
        recv_data = self._recv()
        self._check_cmdanswer(recv_data)

        # データ解析
        word_values = []
        data_index = self._get_answerdata_index()
        for _ in range(readsize):
            value = self.decode_value(
                recv_data[data_index:data_index+self._wordsize],
                "short", self.commtype, signed=True
            )
            word_values.append(value)
            data_index += self._wordsize

        return word_values

    def batchread_bitunits(self, headdevice: str, readsize: int) -> List[int]:
        """
        ビット単位バッチ読み取り

        Args:
            headdevice: 先頭デバイス（例: "M100"）
            readsize: 読み取りビット数

        Returns:
            ビット値リスト（0 or 1）
        """
        command = 0x0401
        subcommand = 0x0003 if self.plctype == iQR_SERIES else 0x0001

        # リクエストデータ作成
        request_data = bytes()
        request_data += self._make_commanddata(command, subcommand)
        request_data += self._make_devicedata(headdevice)
        request_data += self.encode_value(readsize, "short", self.commtype)

        # 送信データ作成・送信
        send_data = self._make_senddata(request_data)
        self._send(send_data)

        # 受信・チェック
        recv_data = self._recv()
        self._check_cmdanswer(recv_data)

        # データ解析
        bit_values = []
        if self.commtype == COMMTYPE_BINARY:
            for i in range(readsize):
                data_index = i // 2 + self._get_answerdata_index()
                value = int.from_bytes(recv_data[data_index:data_index+1], "little")
                # 偶数インデックスは4ビット目、奇数は0ビット目
                if i % 2 == 0:
                    bitvalue = 1 if value & (1 << 4) else 0
                else:
                    bitvalue = 1 if value & (1 << 0) else 0
                bit_values.append(bitvalue)
        else:  # ASCII
            data_index = self._get_answerdata_index()
            for i in range(readsize):
                bitvalue = int(recv_data[data_index:data_index+1].decode())
                bit_values.append(bitvalue)
                data_index += 1

        return bit_values

    # def batchwrite_wordunits(self, headdevice: str, values: List[int]) -> None:
    #     """
    #     ワード単位バッチ書き込み（未使用のため一時コメントアウト）
    #
    #     Args:
    #         headdevice: 先頭デバイス
    #         values: 書き込み値リスト
    #     """
    #     write_size = len(values)
    #     command = 0x1401
    #     subcommand = 0x0002 if self.plctype == iQR_SERIES else 0x0000

    #     # リクエストデータ作成
    #     request_data = bytes()
    #     request_data += self._make_commanddata(command, subcommand)
    #     request_data += self._make_devicedata(headdevice)
    #     request_data += self.encode_value(write_size, "short", self.commtype)

    #     for value in values:
    #         request_data += self.encode_value(value, "short", self.commtype, signed=True)

    #     # 送信データ作成・送信
    #     send_data = self._make_senddata(request_data)
    #     self._send(send_data)

    #     # 受信・チェック
    #     recv_data = self._recv()
    #     self._check_cmdanswer(recv_data)

    # def batchwrite_bitunits(self, headdevice: str, values: List[int]) -> None:
    #     """
    #     ビット単位バッチ書き込み（未使用のため一時コメントアウト）
    #
    #     Args:
    #         headdevice: 先頭デバイス
    #         values: ビット値リスト（0 or 1）
    #     """
    #     write_size = len(values)

    #     # 値チェック
    #     for value in values:
    #         if value not in (0, 1):
    #             raise ValueError("Each value must be 0 or 1")

    #     command = 0x1401
    #     subcommand = 0x0003 if self.plctype == iQR_SERIES else 0x0001

    #     # リクエストデータ作成
    #     request_data = bytes()
    #     request_data += self._make_commanddata(command, subcommand)
    #     request_data += self._make_devicedata(headdevice)
    #     request_data += self.encode_value(write_size, "short", self.commtype)

    #     if self.commtype == COMMTYPE_BINARY:
    #         # ビットデータをバイト配列に変換
    #         bit_data = [0 for _ in range((len(values) + 1) // 2)]
    #         for index, value in enumerate(values):
    #             value_index = index // 2
    #             bit_index = 4 if index % 2 == 0 else 0
    #             bit_value = value << bit_index
    #             bit_data[value_index] |= bit_value
    #         request_data += bytes(bit_data)
    #     else:  # ASCII
    #         for value in values:
    #             request_data += str(value).encode()

    #     # 送信データ作成・送信
    #     send_data = self._make_senddata(request_data)
    #     self._send(send_data)

    #     # 受信・チェック
    #     recv_data = self._recv()
    #     self._check_cmdanswer(recv_data)

    def randomread(self, word_devices: List[str],
                  dword_devices: List[str]) -> Tuple[List[int], List[int]]:
        """
        ランダム読み取り

        Args:
            word_devices: ワードデバイスリスト
            dword_devices: ダブルワードデバイスリスト

        Returns:
            (ワード値リスト, ダブルワード値リスト)
        """
        command = 0x0403
        subcommand = 0x0002 if self.plctype == iQR_SERIES else 0x0000

        word_size = len(word_devices)
        dword_size = len(dword_devices)

        # リクエストデータ作成
        request_data = bytes()
        request_data += self._make_commanddata(command, subcommand)
        request_data += self.encode_value(word_size, "byte", self.commtype)
        request_data += self.encode_value(dword_size, "byte", self.commtype)

        for device in word_devices:
            request_data += self._make_devicedata(device)
        for device in dword_devices:
            request_data += self._make_devicedata(device)

        # 送信データ作成・送信
        send_data = self._make_senddata(request_data)
        self._send(send_data)

        # 受信・チェック
        recv_data = self._recv()
        self._check_cmdanswer(recv_data)

        # データ解析
        data_index = self._get_answerdata_index()
        word_values = []
        dword_values = []

        for _ in word_devices:
            value = self.decode_value(
                recv_data[data_index:data_index+self._wordsize],
                "short", self.commtype, signed=True
            )
            word_values.append(value)
            data_index += self._wordsize

        for _ in dword_devices:
            value = self.decode_value(
                recv_data[data_index:data_index+self._wordsize*2],
                "long", self.commtype, signed=True
            )
            dword_values.append(value)
            data_index += self._wordsize * 2

        return word_values, dword_values

    # def randomwrite(self, word_devices: List[str], word_values: List[int],
    #                dword_devices: List[str], dword_values: List[int]) -> None:
    #     """
    #     ランダム書き込み（未使用のため一時コメントアウト）
    #
    #     Args:
    #         word_devices: ワードデバイスリスト
    #         word_values: ワード値リスト
    #         dword_devices: ダブルワードデバイスリスト
    #         dword_values: ダブルワード値リスト
    #     """
    #     if len(word_devices) != len(word_values):
    #         raise ValueError("word_devices and word_values must be same length")
    #     if len(dword_devices) != len(dword_values):
    #         raise ValueError("dword_devices and dword_values must be same length")

    #     word_size = len(word_devices)
    #     dword_size = len(dword_devices)

    #     command = 0x1402
    #     subcommand = 0x0002 if self.plctype == iQR_SERIES else 0x0000

    #     # リクエストデータ作成
    #     request_data = bytes()
    #     request_data += self._make_commanddata(command, subcommand)
    #     request_data += self.encode_value(word_size, "byte", self.commtype)
    #     request_data += self.encode_value(dword_size, "byte", self.commtype)

    #     for device, value in zip(word_devices, word_values):
    #         request_data += self._make_devicedata(device)
    #         request_data += self.encode_value(value, "short", self.commtype, signed=True)

    #     for device, value in zip(dword_devices, dword_values):
    #         request_data += self._make_devicedata(device)
    #         request_data += self.encode_value(value, "long", self.commtype, signed=True)

    #     # 送信データ作成・送信
    #     send_data = self._make_senddata(request_data)
    #     self._send(send_data)

    #     # 受信・チェック
    #     recv_data = self._recv()
    #     self._check_cmdanswer(recv_data)
