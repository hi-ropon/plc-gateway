"""
PLC Operations
==============

PLC通信の共通ロジック
REST APIとMCPサーバーで共有される処理
"""

import os
import re
import sys
import importlib
from typing import List, Dict, Any, Tuple, Optional

from pymcprotocol import Type3E
from pymcprotocol.mcprotocolerror import MCProtocolError
from device_readers.base_device_reader import DeviceReadResult


class PLCConnectionConfig:
    """PLC接続設定クラス"""

    def __init__(self, ip: str = None, port: int = None, timeout_sec: float = None):
        self.ip = ip or os.getenv("PLC_IP", "127.0.0.1")
        self.port = port or int(os.getenv("PLC_PORT", "5511"))
        self.timeout_sec = timeout_sec or float(os.getenv("PLC_TIMEOUT_SEC", "3.0"))

    def __str__(self):
        return f"PLC({self.ip}:{self.port}, timeout={self.timeout_sec}s)"


class PLCOperations:
    """PLC操作の共通ロジック"""

    def __init__(self, config: PLCConnectionConfig = None):
        self.config = config or PLCConnectionConfig()

    def parse_device_spec(self, device_spec: str) -> Tuple[str, int, int]:
        """
        デバイス指定文字列を解析

        Args:
            device_spec: "D100", "D200:5", "M10", "X1A" 等

        Returns:
            tuple: (device_type, address, length)
        """
        # デバイス:長さ の形式をチェック
        if ":" in device_spec:
            device_part, length_str = device_spec.split(":", 1)
            length = int(length_str)
        else:
            device_part = device_spec
            length = 1

        # デバイス種別とアドレスを抽出（H記法対応）
        if device_part.upper().find("H") > 0:  # H記法の場合（例: YH20）
            h_pos = device_part.upper().find("H")
            device_type = device_part[:h_pos].upper()
            address_str = device_part[h_pos+1:]  # H以降がアドレス
        else:
            match = re.match(r"^([A-Za-z]+)(.+)$", device_part)
            if not match:
                raise ValueError(f"Invalid device specification: {device_spec}")
            device_type = match.group(1).upper()
            address_str = match.group(2)

        # 16進数アドレスの処理（XやYでよく使用）
        if address_str.startswith("0x") or address_str.startswith("0X"):
            address = int(address_str, 16)
        elif device_part.upper().find("H") > 0:  # H記法の場合
            address = int(address_str, 16)
        else:
            # 10進数またはそのまま16進数として解釈を試行
            try:
                address = int(address_str, 10)
            except ValueError:
                try:
                    address = int(address_str, 16)
                except ValueError:
                    raise ValueError(f"Invalid address format: {address_str}")

        return device_type, address, length

    def read_single_device(self, device: str, addr: int, length: int,
                          config: PLCConnectionConfig = None) -> List[int]:
        """
        単一デバイスを読み取り

        Args:
            device: デバイス種別 (D, M, X, Y等)
            addr: アドレス
            length: 読み取り長
            config: PLC接続設定（省略時はデフォルト設定を使用）

        Returns:
            List[int]: 読み取り値リスト

        Raises:
            ValueError: サポートされていないデバイス種別
            MCProtocolError: PLC通信エラー
        """
        if config is None:
            config = self.config

        plc = Type3E(plctype="iQ-R")
        plc.setaccessopt(commtype="binary")
        plc.timer = int(config.timeout_sec * 4)

        try:
            plc.connect(config.ip, config.port)

            upper = device.upper()
            if upper in ("D", "W", "R", "ZR"):
                return plc.batchread_wordunits(f"{upper}{addr}", length)
            elif upper in ("X", "Y", "M"):
                return plc.batchread_bitunits(f"{upper}{addr}", length)
            else:
                raise ValueError(f"Unsupported device type '{device}'")

        finally:
            plc.close()

    def batch_read_devices(self, device_specs: List[str],
                          config: PLCConnectionConfig = None) -> List[DeviceReadResult]:
        """
        複数デバイスを効率的にバッチ読み取り（Strategy Pattern使用）

        Args:
            device_specs: デバイス指定リスト ["D100", "M200", "X30:3"]
            config: PLC接続設定（省略時はデフォルト設定を使用）

        Returns:
            List[DeviceReadResult]: 読み取り結果リスト
        """
        if config is None:
            config = self.config

        # モジュールキャッシュ問題の解決：強制再読み込み
        modules_to_reload = [
            'batch_device_reader',
            'device_readers.base_device_reader',
            'device_readers.bit_device_reader',
            'device_readers.word_device_reader'
        ]

        for module_name in modules_to_reload:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])

        from batch_device_reader import BatchDeviceReader

        if not device_specs:
            return []

        # PLC接続
        plc = Type3E(plctype="iQ-R")
        plc.setaccessopt(commtype="binary")
        plc.timer = int(config.timeout_sec * 4)

        try:
            plc.connect(config.ip, config.port)

            # Strategy Patternを使用したバッチ読み取り
            batch_reader = BatchDeviceReader()
            results = batch_reader.batch_read_devices(plc, device_specs)

            return results

        except Exception as e:
            # PLC接続エラー時は全デバイスエラー扱い
            results = []
            for device_spec in device_specs:
                results.append(DeviceReadResult(
                    device=device_spec,
                    values=[],
                    success=False,
                    error=f"PLC connection error: {str(e)}"
                ))
            return results
        finally:
            plc.close()

    def get_supported_devices(self) -> List[str]:
        """
        サポートされているデバイス種別を取得

        Returns:
            List[str]: サポートデバイスリスト
        """
        return ["D", "W", "R", "ZR", "X", "Y", "M"]

    def validate_device_spec(self, device_spec: str) -> bool:
        """
        デバイス指定文字列の妥当性をチェック

        Args:
            device_spec: デバイス指定文字列

        Returns:
            bool: 妥当性判定結果
        """
        try:
            device_type, address, length = self.parse_device_spec(device_spec)
            return device_type in self.get_supported_devices()
        except (ValueError, TypeError):
            return False

    def test_connection(self, config: PLCConnectionConfig = None) -> Dict[str, Any]:
        """
        PLC接続テスト

        Args:
            config: PLC接続設定（省略時はデフォルト設定を使用）

        Returns:
            Dict[str, Any]: 接続テスト結果
        """
        if config is None:
            config = self.config

        plc = Type3E(plctype="iQ-R")
        plc.setaccessopt(commtype="binary")
        plc.timer = int(config.timeout_sec * 4)

        result = {
            "config": str(config),
            "connected": False,
            "error": None,
            "response_time_ms": None
        }

        try:
            import time
            start_time = time.time()

            plc.connect(config.ip, config.port)

            # 簡単な読み取りテスト（D0を1つ読み取り）
            test_values = plc.batchread_wordunits("D0", 1)

            end_time = time.time()
            result["connected"] = True
            result["response_time_ms"] = round((end_time - start_time) * 1000, 2)
            result["test_read_value"] = test_values[0] if test_values else None

        except Exception as e:
            result["error"] = str(e)
        finally:
            try:
                plc.close()
            except:
                pass

        return result


# ──────────────────── グローバルインスタンス ────────────────────
# デフォルトのPLC操作インスタンス
default_plc_ops = PLCOperations()


# ──────────────────── 互換性関数 ────────────────────
# 既存のgateway.pyとの互換性を保つための関数

def _read_plc(device: str, addr: int, length: int, *, ip: str, port: int) -> List[int]:
    """gateway.pyとの互換性を保つための関数"""
    config = PLCConnectionConfig(ip=ip, port=port)
    return default_plc_ops.read_single_device(device, addr, length, config)


def _batch_read_plc(device_specs: List[str], *, ip: str, port: int) -> List[DeviceReadResult]:
    """gateway.pyとの互換性を保つための関数"""
    config = PLCConnectionConfig(ip=ip, port=port)
    return default_plc_ops.batch_read_devices(device_specs, config)


def _parse_device_spec(device_spec: str) -> Tuple[str, int, int]:
    """gateway.pyとの互換性を保つための関数"""
    return default_plc_ops.parse_device_spec(device_spec)