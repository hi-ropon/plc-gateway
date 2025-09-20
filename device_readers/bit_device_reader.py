"""
Bit Device Reader (Updated)
===========================

ビットデバイス（X, Y, M）読み取りクラス
"""

import logging
from typing import List, Tuple

from device_readers.base_device_reader import DeviceReader, DeviceReadResult

logger = logging.getLogger(__name__)


class BitDeviceReader(DeviceReader):
    """ビットデバイス読み取りクラス"""
    
    def __init__(self):
        super().__init__("bit")
        self.supported_types = {"X", "Y", "M"}
    
    def can_read(self, device_type: str) -> bool:
        """
        ビットデバイスかどうかを判定
        
        Args:
            device_type: デバイス種別
            
        Returns:
            bool: ビットデバイスかどうか
        """
        return device_type.upper() in self.supported_types
    
    def read_single(self, plc, device_spec: str, address: int, length: int) -> DeviceReadResult:
        """
        単一ビットデバイスを読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_spec: デバイス指定文字列
            address: アドレス
            length: 読み取り長
            
        Returns:
            DeviceReadResult: 読み取り結果
        """
        try:
            device_type, _, _ = self.parse_device_spec(device_spec)
            
            if not self.can_read(device_type):
                return DeviceReadResult(
                    device=device_spec,
                    values=[],
                    success=False,
                    error=f"Device type {device_type} not supported by BitDeviceReader"
                )
            
            # PLC からビット値を読み取り
            # デバイス指定文字列を構築（pymcprotocol要件に対応）
            if device_type in ["X", "Y"]:
                # X、Yデバイスは16進アドレス
                # pymcprotocolの要件：16進デバイスでは"Y0FF0"形式が必要
                hex_addr = f"{address:X}"
                if len(hex_addr) >= 3 and hex_addr[0].isalpha():
                    # 先頭が英字の場合、0を挿入（例：FF0 → 0FF0）
                    device_address_str = f"{device_type}0{hex_addr}"
                else:
                    device_address_str = f"{device_type}{hex_addr}"
            else:
                # M、D等は10進アドレス
                device_address_str = f"{device_type}{address}"
            
            if length == 1:
                # 単一ビット読み取り
                value = plc.batchread_bitunits(device_address_str, 1)
                values = [int(value[0])] if value and len(value) > 0 else [0]
            else:
                # 複数ビット読み取り
                values = plc.batchread_bitunits(device_address_str, length)
                values = [int(v) for v in values] if values else [0] * length
            
            logger.debug(f"Bit device read success: {device_spec} -> {values}")
            
            return DeviceReadResult(
                device=device_spec,
                values=values,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Bit device read failed: {device_spec} -> {e}")
            return DeviceReadResult(
                device=device_spec,
                values=[],
                success=False,
                error=str(e)
            )
    
    def read_batch(self, plc, device_requests: List[Tuple[str, int, int]]) -> List[DeviceReadResult]:
        """
        複数ビットデバイスをバッチ読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_requests: デバイス要求リスト [(device_spec, address, length), ...]
            
        Returns:
            List[DeviceReadResult]: 読み取り結果リスト
        """
        results = []
        
        # ビットデバイスは個別読み取り（バッチ読み取りAPIの制限）
        for device_spec, address, length in device_requests:
            try:
                device_type, _, _ = self.parse_device_spec(device_spec)
                
                if not self.can_read(device_type):
                    results.append(DeviceReadResult(
                        device=device_spec,
                        values=[],
                        success=False,
                        error=f"Device type {device_type} not supported"
                    ))
                    continue
                
                result = self.read_single(plc, device_spec, address, length)
                results.append(result)
                
            except Exception as e:
                results.append(DeviceReadResult(
                    device=device_spec,
                    values=[],
                    success=False,
                    error=str(e)
                ))
        
        logger.info(f"Bit batch read completed: {len(device_requests)} devices")
        return results
    
    def _optimize_bit_reads(self, device_requests: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        """
        ビット読み取り要求を最適化（連続アドレスをまとめる）
        
        Args:
            device_requests: 元のデバイス要求リスト
            
        Returns:
            List[Tuple[str, int, int]]: 最適化されたデバイス要求リスト
        """
        # 将来的な最適化: 連続するアドレスをまとめて読み取り
        # 現在は単純に元のリストを返す
        return device_requests