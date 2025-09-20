"""
Batch Device Reader
==================

複数デバイスのバッチ読み取りを管理するメインクラス
Strategy Patternを使用してデバイス別の読み取り処理を委譲
"""

import logging
from typing import List, Dict, Any
from device_readers.base_device_reader import DeviceReaderRegistry, DeviceReadResult
from device_readers.word_device_reader import WordDeviceReader
from device_readers.bit_device_reader import BitDeviceReader

logger = logging.getLogger(__name__)


class BatchDeviceReader:
    """複数デバイスバッチ読み取りクラス（Strategy Pattern使用）"""
    
    def __init__(self):
        """デバイスリーダーレジストリを初期化"""
        self.registry = DeviceReaderRegistry()
        
        # デバイスリーダーを登録
        self.registry.register(WordDeviceReader())
        self.registry.register(BitDeviceReader())
        
        logger.info(f"BatchDeviceReader初期化完了(v2) - サポートデバイス: {self.registry.get_supported_types()}")
    
    def batch_read_devices(self, plc, device_specs: List[str]) -> List[DeviceReadResult]:
        """
        複数デバイスを効率的にバッチ読み取り
        
        Args:
            plc: PLC接続オブジェクト
            device_specs: デバイス指定リスト ["D100", "M200", "X30:3"]
            
        Returns:
            List[DeviceReadResult]: 読み取り結果リスト
        """
        if not device_specs:
            logger.warning("デバイス指定が空です")
            return []
        
        # デバイス種別ごとにグループ化
        device_groups = self._group_devices_by_reader(device_specs)
        
        results = []
        
        # デバイス種別ごとに最適化されたバッチ読み取りを実行
        for reader_type, device_requests in device_groups.items():
            try:
                # 最初のデバイス要求を使ってリーダーを特定
                if device_requests:
                    first_device_spec, _, _ = device_requests[0]
                    device_type, _, _ = self._parse_device_spec(first_device_spec)
                    reader = self.registry.get_reader(device_type)
                    batch_results = reader.read_batch(plc, device_requests)
                    results.extend(batch_results)
                    
                    logger.debug(f"{reader_type}デバイス読み取り完了: {len(device_requests)}個")
                
            except ValueError as e:
                # サポートされていないデバイス種別
                logger.error(f"未サポートデバイス種別: {reader_type} - {e}")
                for device_spec, _, _ in device_requests:
                    results.append(DeviceReadResult(
                        device=device_spec,
                        values=[],
                        success=False,
                        error=f"Unsupported device type: {reader_type}"
                    ))
            except Exception as e:
                # その他のエラー
                logger.error(f"{reader_type}デバイス読み取りエラー: {e}")
                for device_spec, _, _ in device_requests:
                    results.append(DeviceReadResult(
                        device=device_spec,
                        values=[],
                        success=False,
                        error=str(e)
                    ))
        
        # 元の順序に並び替え
        ordered_results = self._reorder_results(results, device_specs)
        
        logger.info(f"バッチ読み取り完了: {len(device_specs)}デバイス, 成功: {sum(1 for r in ordered_results if r.success)}個")
        
        return ordered_results
    
    def _group_devices_by_reader(self, device_specs: List[str]) -> Dict[str, List[tuple]]:
        """
        デバイス指定をリーダー種別ごとにグループ化
        
        Args:
            device_specs: デバイス指定リスト
            
        Returns:
            Dict[str, List[tuple]]: {reader_type: [(device_spec, address, length), ...]}
        """
        groups = {}
        
        for device_spec in device_specs:
            try:
                # デバイス指定を解析
                device_type, address, length = self._parse_device_spec(device_spec)
                
                # 対応するリーダーを探す
                try:
                    reader = self.registry.get_reader(device_type)
                    reader_key = reader.device_type
                    
                    if reader_key not in groups:
                        groups[reader_key] = []
                    
                    groups[reader_key].append((device_spec, address, length))
                    
                except ValueError:
                    # 未サポートデバイス - 個別グループとして扱う
                    groups[device_type] = groups.get(device_type, [])
                    groups[device_type].append((device_spec, address, length))
                    
            except Exception as e:
                logger.error(f"デバイス解析エラー: {device_spec} - {e}")
                # エラーデバイスも個別グループとして記録
                error_key = f"error_{device_spec}"
                groups[error_key] = [(device_spec, 0, 1)]
        
        logger.debug(f"デバイスグルーピング完了: {dict((k, len(v)) for k, v in groups.items())}")
        return groups
    
    def _parse_device_spec(self, device_spec: str) -> tuple:
        """
        デバイス指定文字列を解析（base_device_readerの実装を使用）
        
        Args:
            device_spec: デバイス指定文字列
            
        Returns:
            tuple: (device_type, address, length)
        """
        # BitDeviceReaderから継承したparse_device_specメソッドを使用
        from device_readers.bit_device_reader import BitDeviceReader
        temp_reader = BitDeviceReader()
        return temp_reader.parse_device_spec(device_spec)
    
    def _reorder_results(self, results: List[DeviceReadResult], original_order: List[str]) -> List[DeviceReadResult]:
        """
        結果を元のデバイス指定順序に並び替え
        
        Args:
            results: 読み取り結果リスト
            original_order: 元のデバイス指定順序
            
        Returns:
            List[DeviceReadResult]: 並び替えられた結果リスト
        """
        # デバイス指定 -> 結果のマッピングを作成
        result_map = {result.device: result for result in results}
        
        # 元の順序で結果を並び替え
        ordered_results = []
        for device_spec in original_order:
            if device_spec in result_map:
                ordered_results.append(result_map[device_spec])
            else:
                # 結果が見つからない場合はエラー結果を作成
                ordered_results.append(DeviceReadResult(
                    device=device_spec,
                    values=[],
                    success=False,
                    error="No result found"
                ))
        
        return ordered_results
    
    def get_supported_device_types(self) -> List[str]:
        """
        サポートされているデバイス種別を取得
        
        Returns:
            List[str]: サポートデバイス種別リスト
        """
        return self.registry.get_supported_types()