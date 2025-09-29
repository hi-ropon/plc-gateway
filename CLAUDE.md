# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 重要な指示

**このプロジェクトでは日本語でやり取りしてください。** コメント、ドキュメント、コミットメッセージ、およびユーザーとの会話はすべて日本語で行うこと。

## 概要

このプロジェクトは三菱PLCとMCプロトコルで通信するための統合Gateway APIです。以下の3つの方法でPLCデバイスにアクセス可能：

1. **FastAPI REST API** - HTTP経由でのPLCデバイス読み取り
2. **OpenAPI仕様出力** - 標準的なAPI仕様ファイル（JSON/YAML）の生成・ダウンロード
3. **MCPサーバー** - AI統合用Model Context Protocol対応

## アーキテクチャ

### 主要コンポーネント

1. **gateway.py** - FastAPIアプリケーションのメインエントリーポイント
   - PLC通信API（単一デバイス読み取り、バッチ読み取り）
   - OpenAPI仕様の強化（サーバー情報、コンタクト情報、ライセンス等）
   - 起動時のOpenAPI仕様ファイル自動生成（JSON/YAML）
   - OpenAPI仕様ダウンロードエンドポイント
   - CORS設定でCopilot Studioからのアクセスを許可

2. **mcp_server.py** - Model Context Protocol サーバー実装
   - AI統合用MCPツール（6種類のツールを提供）
   - stdio経由でのMCPクライアント通信
   - PLC操作の共通ロジックを使用

3. **plc_operations.py** - 共通PLC操作ロジック
   - REST APIとMCPサーバー間で共有される処理
   - PLCConnectionConfigクラスで接続設定を管理
   - エラーハンドリングと接続テスト機能

4. **main.py** - 統合起動スクリプト
   - FastAPI、MCPサーバー、または両方の同時起動
   - コマンドライン引数での柔軟な起動オプション
   - サービス管理とシャットダウン処理

5. **batch_device_reader.py** - 複数デバイス一括読み取りの管理
   - Strategy Patternを使用してデバイス種別ごとの処理を委譲
   - 効率的なMCプロトコルrandomread機能を活用

6. **device_readers/** - デバイス読み取り戦略の実装
   - `base_device_reader.py`: 抽象基底クラスとレジストリ
   - `word_device_reader.py`: ワードデバイス（D, W, R, ZR）対応
   - `bit_device_reader.py`: ビットデバイス（X, Y, M）対応

7. **mcp_gateway_bridge.py** - Copilot Studio統合用HTTPブリッジ
   - HTTPリクエストをMCPプロトコルに変換
   - 別ポート（8001）で起動
   - Copilot Studioからの直接アクセスをサポート

8. **network_utils.py** - ネットワークユーティリティ
   - ローカルIPアドレス取得
   - ホスト名取得
   - OpenAPIサーバー情報生成

9. **version.py** - バージョン管理
   - システムバージョン情報
   - コンポーネントバージョン管理
   - 依存ライブラリバージョン確認

### 設計パターン

- **Strategy Pattern**: デバイス種別に応じた読み取り処理の実装
- **Registry Pattern**: デバイスリーダーの動的登録と取得
- **Factory Pattern**: デバイス指定文字列の解析と適切なリーダー選択
- **Bridge Pattern**: HTTP-MCP間のプロトコル変換

## 開発コマンド

### 統合起動（推奨）
```bash
# REST API + MCPサーバー同時起動
python main.py --rest-api --mcp-server

# REST APIのみ
python main.py --rest-api

# MCPサーバーのみ
python main.py --mcp-server
```

### 個別起動
```bash
# FastAPI REST API起動
uvicorn gateway:app --reload --host 0.0.0.0 --port 8000

# MCPサーバー起動
python mcp_server.py

```

### 依存関係インストール
```bash
pip install -r requirements.txt
```

### 環境変数設定
```bash
export PLC_IP=192.168.1.100      # PLCのIPアドレス（デフォルト: 127.0.0.1）
export PLC_PORT=5511             # PLCのポート番号（デフォルト: 5511）
export PLC_TIMEOUT_SEC=3.0       # タイムアウト秒数（デフォルト: 3.0）
export MCP_LOG_LEVEL=INFO        # MCPログレベル（デフォルト: INFO）
```

## サポートデバイス

### ワードデバイス
- D: データレジスタ
- W: リンクレジスタ
- R: ファイルレジスタ
- ZR: インデックスレジスタ

### ビットデバイス
- X: 入力リレー（16進アドレス）
- Y: 出力リレー（16進アドレス）
- M: 内部リレー（10進アドレス）

### デバイス指定形式
- 単一デバイス: `D100`, `M200`, `X1A`
- 連続読み取り: `D100:5`, `M200:3`
- 16進アドレス: `X1A`, `Y0FF0`, `XH1A`（H記法）

## API エンドポイント

### REST API エンドポイント

#### 単一デバイス読み取り
- `POST /api/read` - JSON形式でリクエスト
- `GET /api/read/{device}/{addr}/{length}` - URLパラメータ形式
- `GET /{device}/{addr}/{length}` - 後方互換性対応

#### バッチ読み取り
- `POST /api/batch_read` - 複数デバイスを一括読み取り
- `GET /api/batch_read_status` - バッチ読み取り機能の状態確認

#### OpenAPI仕様ファイル
- `GET /api/openapi/json` - JSON形式のOpenAPI仕様ダウンロード
- `GET /api/openapi/yaml` - YAML形式のOpenAPI仕様ダウンロード
- `GET /api/openapi/status` - OpenAPI仕様生成機能の状態確認

#### バージョン情報
- `GET /api/version` - システムバージョン情報の取得

### MCPツール（AI統合用）

#### 利用可能なツール
- `read_plc_device`: 単一デバイス読み取り
- `batch_read_plc`: 複数デバイス一括読み取り
- `parse_device_spec`: デバイス指定文字列解析
- `get_supported_devices`: サポートデバイス一覧取得
- `test_plc_connection`: PLC接続テスト
- `validate_device_spec`: デバイス指定妥当性チェック

## 技術仕様

### MCプロトコル通信
- 独自実装のmcprotocolライブラリを使用
- iQ-R PLCに最適化
- binaryモードで通信
- randomread機能でバッチ読み取りを最適化

### エラーハンドリング
- デバイス種別ごとの専用エラーメッセージ
- PLC接続エラー時の適切なフォールバック
- 個別デバイス読み取り失敗時の部分的成功対応

### パフォーマンス最適化
- バッチ読み取りでMCプロトコルの効率性を活用
- 同種デバイスのグルーピング
- 失敗時の個別読み取りフォールバック機能

## 重要な注意事項

### テスト実行
このプロジェクトには現在テストフレームワークが設定されていません。コードを変更する際は、手動でのテストが必要です。

### デバッグとログ
- デバイス読み取り処理にはPythonの`logging`モジュールを使用
- デバッグレベルのログでデバイス解析結果を確認可能
- PLC接続エラーは適切にキャッチされ、HTTPエラーレスポンスとして返される

### ファイル構造の変更
このプロジェクトでは以下のファイルが削除されています：
- `plc_filecontrol.py`: MCプロトコル1827/1828/182Aを使用したファイル制御機能は現在未実装

### 起動時処理
- **OpenAPI仕様ファイル自動生成**: 起動時に`openapi.json`と`openapi.yaml`を自動生成
- **起動情報表示**: PLC設定、利用可能エンドポイントの情報を表示

### モジュール再読み込み
バッチ読み取り時に関連モジュールの強制再読み込みを実行してキャッシュ問題に対応。

### 統合起動システム
- **サービス管理**: REST APIとMCPサーバーの同時管理
- **シグナルハンドリング**: 適切なシャットダウン処理
- **ログ出力**: 構造化された起動・停止ログ

### バージョン情報
- **現在のバージョン**: v1.2.0 (2025-01-20)
- **最新機能**:
  - バージョン表示機能追加
  - 統合起動システム改善
  - 開発/本番モード分離機能
  - ネットワーク診断機能追加

## 今後の開発予定

### セキュリティ強化（TODO）

#### プライベートIPアドレス制限機能
- **対象**: 本番モード（`--production`）での外部アクセス制御
- **目的**: 企業環境での万が一の場合のセキュリティ強化
- **実装予定**:
  - プライベートネットワーク範囲の自動判定
    - `192.168.0.0/16` (クラスC)
    - `10.0.0.0/8` (クラスA)
    - `172.16.0.0/12` (クラスB)
    - `127.0.0.0/8` (ローカルホスト)
  - 設定可能な許可IPレンジ
  - パブリックIPからのアクセス拒否
  - アクセスログの強化

#### 実装方針
```bash
# 将来の使用例
export ALLOWED_IP_RANGES="192.168.0.0/24,10.1.0.0/16"
python main.py --rest-api --production --ip-restrict

# または
python main.py --rest-api --production --private-only
```

#### 技術仕様
- FastAPIミドルウェアでのIPアドレスチェック
- `ipaddress`モジュールを使用したCIDR範囲チェック
- 拒否時のHTTP 403 Forbiddenレスポンス
- 詳細なアクセスログとブロックログ

**注意**: 現在は前段のファイアウォールでセキュリティを確保しており、この機能は多層防御の一環として将来実装予定。