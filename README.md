# PLC Gateway API

三菱PLCとMCプロトコルで通信するためのFastAPIベースのGateway API

## 概要

このプロジェクトは、三菱電機のPLC（Programmable Logic Controller）とMCプロトコルを使用して通信を行うRESTful APIゲートウェイです。Copilot Studioなどの外部ツールからPLCデバイスの読み取りを簡単に行うことができます。

## 主な機能

- **単一デバイス読み取り**: 指定したPLCデバイスから値を読み取り
- **バッチ読み取り**: 複数のPLCデバイスを一括で効率的に読み取り
- **多様なデバイス対応**: ワードデバイス（D, W, R, ZR）とビットデバイス（X, Y, M）をサポート
- **柔軟なアドレス指定**: 10進数・16進数・H記法に対応
- **CORS対応**: 外部ツールからのアクセスを許可

## サポートデバイス

### ワードデバイス
- **D**: データレジスタ
- **W**: リンクレジスタ
- **R**: ファイルレジスタ
- **ZR**: インデックスレジスタ

### ビットデバイス
- **X**: 入力リレー（16進アドレス）
- **Y**: 出力リレー（16進アドレス）
- **M**: 内部リレー（10進アドレス）

### デバイス指定形式
```
D100        # 単一デバイス
D100:5      # 連続5個読み取り
X1A         # 16進アドレス
M0x10       # 16進プレフィックス
YH20        # 16進H記法
```

## インストール

### 必要要件
- Python 3.8以上
- 三菱電機のiQ-R PLC

### 依存関係のインストール
```bash
pip install -r requirements.txt
```

## 使用方法

### アプリケーションの起動
```bash
uvicorn gateway:app --reload --host 0.0.0.0 --port 8000
```

### 環境変数での設定
```bash
export PLC_IP=192.168.1.100        # PLCのIPアドレス
export PLC_PORT=5511               # PLCのポート番号
export PLC_TIMEOUT_SEC=3.0         # タイムアウト秒数
```

## API エンドポイント

### 単一デバイス読み取り

#### POST `/api/read`
```json
{
    "device": "D",
    "addr": 100,
    "length": 1,
    "ip": "192.168.1.100",     // オプション
    "port": 5511               // オプション
}
```

#### GET `/api/read/{device}/{addr}/{length}`
```
GET /api/read/D/100/1?ip=192.168.1.100&port=5511
```

### バッチ読み取り

#### POST `/api/batch_read`
```json
{
    "devices": ["D100", "D200:5", "M10", "X1A", "YH20"],
    "ip": "192.168.1.100",     // オプション
    "port": 5511               // オプション
}
```

#### レスポンス例
```json
{
    "results": [
        {
            "device": "D100",
            "values": [12345],
            "success": true,
            "error": null
        },
        {
            "device": "M10",
            "values": [1],
            "success": true,
            "error": null
        }
    ],
    "total_devices": 2,
    "successful_devices": 2
}
```

### システム状態確認

#### GET `/api/batch_read_status`
バッチ読み取り機能のサポート状況と制限事項を取得

## 技術仕様

### 使用技術
- **FastAPI**: 高性能なWebフレームワーク
- **pymcprotocol**: 三菱PLCのMCプロトコル通信ライブラリ
- **Pydantic**: データバリデーション
- **Uvicorn**: ASGIサーバー

### アーキテクチャ
- **Strategy Pattern**: デバイス種別に応じた読み取り処理
- **Registry Pattern**: デバイスリーダーの動的管理
- **バッチ最適化**: MCプロトコルのrandomread機能を活用

### パフォーマンス
- 最大32デバイス/リクエストでバッチ読み取り対応
- 失敗時の個別読み取りフォールバック
- 効率的なMCプロトコル通信

## 開発

### プロジェクト構造
```
gateway/
├── gateway.py                 # メインアプリケーション
├── batch_device_reader.py     # バッチ読み取り管理
├── device_readers/            # デバイス読み取り戦略
│   ├── base_device_reader.py  # 基底クラス
│   ├── word_device_reader.py  # ワードデバイス
│   └── bit_device_reader.py   # ビットデバイス
├── requirements.txt           # 依存関係
├── CLAUDE.md                 # Claude Code用ガイド
└── README.md                 # このファイル
```

### API ドキュメント
アプリケーション起動後、以下のURLでSwagger UIにアクセス可能：
```
http://localhost:8000/docs
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。