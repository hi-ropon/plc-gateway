"""
Word Device Reader
==================

ワードデバイス（D, W, R, ZR）読み取りクラス
"""

import logging
from typing import List, Tuple

from device_readers.base_device_reader import DeviceReader, DeviceReadResult

logger = logging.getLogger(__name__)


class WordDeviceReader(DeviceReader):
    """ワードデバイス読み取りクラス"""
    
    def __init__(self):
        super().__init__("word")
        self.supported_types = {"D", "W", "R", "ZR"}
    
    def can_read(self, device_type: str) -> bool:
        """
        ワードデバイスかどうかを判定
        
        Args:
            device_type: デバイス種別
            
        Returns:
            bool: ワードデバイスかどうか
        """
        return device_type.upper() in self.supported_types
    
    def read_single(self, plc, device_spec: str, address: int, length: int) -> DeviceReadResult:
        """
        単一ワードデバイスを読み取り
        
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
                    error=f"Device type {device_type} not supported by WordDeviceReader"
                )
            
            # PLC から値を読み取り
            values = plc.batchread_wordunits(f"{device_type}{address}", length)
            
            logger.debug(f"Word device read success: {device_spec} -> {values}")
            
            return DeviceReadResult(
                device=device_spec,
                values=values,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Word device read failed: {device_spec} -> {e}")
            return DeviceReadResult(
                device=device_spec,
                values=[],
                success=False,
                error=str(e)
            )
    
    def read_batch(self, plc, device_requests: List[Tuple[str, int, int]]) -> List[DeviceReadResult]:
        """
        複数ワードデバイスをバッチ読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_requests: デバイス要求リスト [(device_spec, address, length), ...]
            
        Returns:
            List[DeviceReadResult]: 読み取り結果リスト
        """
        results = []
        
        # バッチ読み取り対象のデバイスリストを作成
        word_devices = []
        device_mapping = {}  # word_devices のインデックスとオリジナル要求のマッピング
        
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
                
                # バッチ読み取り用のデバイスリストに追加
                start_index = len(word_devices)
                for i in range(length):
                    word_devices.append(f"{device_type}{address + i}")
                
                device_mapping[device_spec] = (start_index, length)
                
            except Exception as e:
                results.append(DeviceReadResult(
                    device=device_spec,
                    values=[],
                    success=False,
                    error=str(e)
                ))
        
        # バッチ読み取り実行
        if word_devices:
            try:
                # randomread を使用してバッチ読み取り
                word_values, _ = plc.randomread(word_devices, [])  # dword_devices は空
                
                # 結果をデバイス指定別に整理
                for device_spec, (start_index, length) in device_mapping.items():
                    values = word_values[start_index:start_index + length]
                    results.append(DeviceReadResult(
                        device=device_spec,
                        values=values,
                        success=True
                    ))
                
                logger.info(f"Word batch read success: {len(word_devices)} devices")
                
            except Exception as e:
                logger.warning(f"Word batch read failed, falling back to individual reads: {e}")
                
                # バッチ読み取り失敗時は個別読み取りにフォールバック
                for device_spec, address, length in device_requests:
                    if device_spec in device_mapping:
                        result = self.read_single(plc, device_spec, address, length)
                        results.append(result)
        
        return results