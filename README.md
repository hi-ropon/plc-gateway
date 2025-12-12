# PLC Gateway API

三菱PLCとMCプロトコルで通信するための統合Gateway API。FastAPI REST APIでPLCデバイスにアクセスできます。

## 🚀 機能概要

- **FastAPI REST API**: HTTP経由でPLCデバイス読み取り
- **バッチ読み取り**: 複数デバイスの効率的な一括読み取り
- **統合起動システム**: 個別起動または統合起動
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

## 🛠 インストール

### 1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 2. 環境変数設定（オプション）
```bash
export PLC_IP=192.168.1.100      # PLCのIPアドレス (デフォルト: 127.0.0.1)
export PLC_PORT=5511             # PLCのポート番号 (デフォルト: 5511)
export PLC_TIMEOUT_SEC=3.0       # タイムアウト秒数 (デフォルト: 3.0)
```

## 🚀 起動方法

### 統合起動（推奨）
```bash
# 開発モード（ホットリロード）
python main.py

# 本番モード（外部アクセス許可）
python main.py --production

# カスタムポートで起動
python main.py --port 9000
```

### uvicorn での直接起動

#### FastAPI REST API
```bash
uvicorn gateway:app --reload --host 0.0.0.0 --port 8000
```

## 🧱 PyInstaller ビルド（1ファイル形式）

1. 依存と PyInstaller をインストール
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```
2. ルート直下の `production_launcher.spec` を使ってビルド
   ```bash
   pyinstaller --clean production_launcher.spec
   ```
   - もしくは直接コマンド指定:  
     `pyinstaller --clean --onefile --name plc_gateway_prod production_launcher.py`
3. `dist/plc_gateway_prod.exe` が生成される。ユーザーへはこの exe のみを配布すればよい（ダブルクリックで本番モードが起動）。
4. アイコンや追加データを同梱したい場合は `production_launcher.spec` 内の `datas` や `icon` を編集して再ビルドする。

## 📚 利用方法

### 1. FastAPI REST API

#### 単一デバイス読み取り
```bash
# GET方式
curl "http://localhost:8000/api/read/D/100/1"

# POST方式
curl -X POST "http://localhost:8000/api/read" \
  -H "Content-Type: application/json" \
  -d '{"device": "D", "addr": 100, "length": 1}'
```

#### バッチ読み取り
```bash
curl -X POST "http://localhost:8000/api/batch_read" \
  -H "Content-Type: application/json" \
  -d '{"devices": ["D100", "M200:3", "X1A"]}'
```

#### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🎯 使用例

### REST API使用例

```python
import requests

# 単一デバイス読み取り
response = requests.post('http://localhost:8000/api/read',
    json={'device': 'D', 'addr': 100, 'length': 1})
print(response.json())  # {'values': [42]}

# バッチ読み取り
response = requests.post('http://localhost:8000/api/batch_read',
    json={'devices': ['D100', 'M200:3', 'X1A']})
result = response.json()
print(f"成功: {result['successful_devices']}/{result['total_devices']}")
```

## API エンドポイント詳細

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

## 🏗 アーキテクチャ

```
gateway/
├── gateway.py              # FastAPI REST API
├── plc_operations.py      # 共通PLC操作ロジック
├── main.py               # 統合起動スクリプト
├── batch_device_reader.py # バッチ読み取り管理
├── network_utils.py       # ネットワークユーティリティ
├── version.py            # バージョン管理
├── device_readers/       # デバイス読み取り戦略
│   ├── base_device_reader.py
│   ├── word_device_reader.py
│   └── bit_device_reader.py
├── requirements.txt      # 依存関係
├── CLAUDE.md           # Claude Code用ガイド
└── README.md           # このファイル
```

### 設計パターン
- **Strategy Pattern**: デバイス種別ごとの読み取り処理
- **Registry Pattern**: デバイスリーダーの動的登録
- **Factory Pattern**: デバイス指定文字列の解析

## ⚙️ 設定オプション

### 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `PLC_IP` | 127.0.0.1 | PLCのIPアドレス |
| `PLC_PORT` | 5511 | PLCのポート番号 |
| `PLC_TIMEOUT_SEC` | 3.0 | 通信タイムアウト（秒） |

### 起動オプション

#### main.py オプション
```bash
python main.py --help

  --rest-api          FastAPI REST APIを起動
  --host HOST         REST APIバインドホスト (デフォルト: 0.0.0.0)
  --port PORT         REST APIポート番号 (デフォルト: 8000)
  --production        0.0.0.0でバインドして外部アクセスを許可
  --no-reload         ホットリロードを無効化
  --log-level LEVEL   ログレベル (DEBUG/INFO/WARNING/ERROR)
```

## 🔧 トラブルシューティング

### よくある問題

#### 1. PLC接続エラー
```bash
# 接続テストの実行
curl "http://localhost:8000/api/batch_read_status"

# 環境変数の確認
echo $PLC_IP $PLC_PORT
```

#### 2. デバイス指定エラー
```bash
# デバイス指定の妥当性確認
curl -X POST "http://localhost:8000/api/read" \
  -H "Content-Type: application/json" \
  -d '{"device": "D", "addr": 100, "length": 1}'
```

### ログ出力例

```
2024-01-01 12:00:00 - plc-gateway-launcher - INFO - 🚀 すべてのサービスが正常に起動しました
2024-01-01 12:00:00 - plc-gateway-launcher - INFO - 🌐 FastAPI REST API: http://0.0.0.0:8000
2024-01-01 12:00:00 - plc-gateway-launcher - INFO - 📡 PLC設定: 127.0.0.1:5511 (timeout: 3.0s)
```

## 📄 ライセンス

MIT License

---

**注意**: 本番環境では適切なセキュリティ設定（CORS制限、認証等）を行ってください。
