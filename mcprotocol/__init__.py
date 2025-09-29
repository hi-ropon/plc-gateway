"""
MC Protocol Implementation
==========================

独自実装のMCプロトコル通信ライブラリ
pymcprotocolの依存を排除し、必要最小限の機能を実装

主要コンポーネント:
- Type3E: 3Eフレーム通信クラス
- DeviceConstants: デバイス定数定義
- MCProtocolError: エラー処理

Version: 1.0.0
Author: Gateway Project
"""

__version__ = '1.0.0'
__author__ = 'Gateway Project'

from .protocol_3e import Type3E
from .constants import DeviceConstants
from .errors import MCProtocolError

__all__ = ['Type3E', 'DeviceConstants', 'MCProtocolError']