"""
Base Device Reader
==================

デバイス読み取りの基底クラス
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional
from pydantic import BaseModel


class DeviceReadResult(BaseModel):
    """デバイス読み取り結果"""
    device: str
    values: List[Any]
    success: bool
    error: Optional[str] = None


class DeviceReader(ABC):
    """デバイス読み取りの抽象基底クラス"""
    
    def __init__(self, device_type: str):
        """
        デバイスリーダーを初期化
        
        Args:
            device_type: デバイス種別（D, M, X, Y等）
        """
        self.device_type = device_type
    
    @abstractmethod
    def can_read(self, device_type: str) -> bool:
        """
        指定されたデバイス種別を読み取れるかを判定
        
        Args:
            device_type: デバイス種別
            
        Returns:
            bool: 読み取り可能かどうか
        """
        pass
    
    @abstractmethod
    def read_single(self, plc, device_spec: str, address: int, length: int) -> DeviceReadResult:
        """
        単一デバイスを読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_spec: デバイス指定文字列
            address: アドレス
            length: 読み取り長
            
        Returns:
            DeviceReadResult: 読み取り結果
        """
        pass
    
    @abstractmethod
    def read_batch(self, plc, device_requests: List[Tuple[str, int, int]]) -> List[DeviceReadResult]:
        """
        複数デバイスをバッチ読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_requests: デバイス要求リスト [(device_spec, address, length), ...]
            
        Returns:
            List[DeviceReadResult]: 読み取り結果リスト
        """
        pass
    
    def parse_device_spec(self, device_spec: str) -> Tuple[str, int, int]:
        """
        デバイス指定文字列を解析
        
        Args:
            device_spec: デバイス指定文字列 ("D100", "M200:3")
            
        Returns:
            Tuple[str, int, int]: (デバイス種別, アドレス, 長さ)
        """
        import re
        
        # デバイス指定の解析（16進対応）
        # デバイス:長さ の形式をチェック
        if ":" in device_spec:
            device_part, length_str = device_spec.split(":", 1)
            length = int(length_str)
        else:
            device_part = device_spec
            length = 1
        
        # 既知のPLCデバイス種別を明示的にチェック（長いデバイス名を優先）
        known_devices = [
            # 2文字デバイス（特殊デバイス・特別リレー/レジスタ）
            "SM", "SD", "CN", "CC", "CS", "CX", "TN", "TC", "TS", "TX", "SB", "SW", "DX", "DY",
            # 1文字デバイス（標準的なPLCデバイス）
            "X", "Y", "B", "M", "D", "T", "C", "Z", "H", "L", "F", "V", "R", "W", "S", "U", "N",
        ]
        
        device_type = None
        address_str = None
        
        # 既知デバイス種別を順番にチェック
        for known_device in known_devices:
            if device_part.upper().startswith(known_device):
                # アドレス部分が有効かチェック
                potential_address = device_part[len(known_device):]
                if potential_address and re.match(r"^[0-9A-Fa-f]+$", potential_address):
                    device_type = known_device
                    address_str = potential_address
                    break
        
        if device_type is None:
            # より詳細なエラーメッセージを提供
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"デバイス解析失敗: '{device_spec}' - 認識されないデバイス形式")
            raise ValueError(f"Invalid device specification: {device_spec} - 対応デバイス: X,Y,B,M,D,T,C,Z,H,L,F,V,R,W,S,U,N,SM,SD等")
        
        # アドレス変換
        hex_devices = {"X", "Y", "B"}  # 16進アドレスを採用するデバイス
        if device_type in hex_devices:
            address = int(address_str, 16)
        else:
            address = int(address_str, 10)
        
        # 成功時のデバッグログ
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"デバイス解析成功: '{device_spec}' -> device_type='{device_type}', address={address} (0x{address:X}), length={length}")
        
        return device_type, address, length


class DeviceReaderRegistry:
    """デバイスリーダー登録管理クラス"""
    
    def __init__(self):
        self._readers: List[DeviceReader] = []
    
    def register(self, reader: DeviceReader):
        """
        デバイスリーダーを登録
        
        Args:
            reader: 登録するデバイスリーダー
        """
        self._readers.append(reader)
    
    def get_reader(self, device_type: str) -> DeviceReader:
        """
        指定されたデバイス種別に対応するリーダーを取得
        
        Args:
            device_type: デバイス種別
            
        Returns:
            DeviceReader: 対応するデバイスリーダー
            
        Raises:
            ValueError: 対応するリーダーが見つからない場合
        """
        for reader in self._readers:
            if reader.can_read(device_type):
                return reader
        
        raise ValueError(f"No reader found for device type: {device_type}")
    
    def get_supported_types(self) -> List[str]:
        """
        サポートされているデバイス種別のリストを取得
        
        Returns:
            List[str]: サポートされているデバイス種別
        """
        supported_types = []
        for reader in self._readers:
            supported_types.append(reader.device_type)
        return supported_types
