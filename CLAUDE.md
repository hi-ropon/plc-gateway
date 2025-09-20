# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

このプロジェクトは三菱PLCとMCプロトコルで通信するためのFastAPIベースのGateway APIです。Copilot Studioなどの外部ツールからPLCデバイスの読み取りを可能にします。

## アーキテクチャ

### 主要コンポーネント

1. **gateway.py** - FastAPIアプリケーションのメインエントリーポイント
   - PLC通信API（単一デバイス読み取り、バッチ読み取り）
   - CORS設定でCopilot Studioからのアクセスを許可
   - 環境変数でPLC接続設定を管理

2. **plc_filecontrol.py** - PLCファイル制御専用ユーティリティ
   - MCプロトコル 1827/1828/182A を使用
   - ファイルのロック、読み取り、クローズ機能

3. **batch_device_reader.py** - 複数デバイス一括読み取りの管理
   - Strategy Patternを使用してデバイス種別ごとの処理を委譲
   - 効率的なMCプロトコルrandomread機能を活用

4. **device_readers/** - デバイス読み取り戦略の実装
   - `base_device_reader.py`: 抽象基底クラスとレジストリ
   - `word_device_reader.py`: ワードデバイス（D, W, R, ZR）対応
   - `bit_device_reader.py`: ビットデバイス（X, Y, M）対応

### 設計パターン

- **Strategy Pattern**: デバイス種別に応じた読み取り処理の実装
- **Registry Pattern**: デバイスリーダーの動的登録と取得
- **Factory Pattern**: デバイス指定文字列の解析と適切なリーダー選択

## 開発コマンド

### アプリケーション実行
```bash
uvicorn gateway:app --reload --host 0.0.0.0 --port 8000
```

### 依存関係インストール
```bash
pip install -r requirements.txt
```

### PLC接続設定
環境変数で設定可能：
- `PLC_IP`: PLCのIPアドレス（デフォルト: 127.0.0.1）
- `PLC_PORT`: PLCのポート番号（デフォルト: 5511）
- `PLC_TIMEOUT_SEC`: タイムアウト秒数（デフォルト: 3.0）

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

### 単一デバイス読み取り
- `POST /api/read` - JSON形式でリクエスト
- `GET /api/read/{device}/{addr}/{length}` - URLパラメータ形式
- `GET /{device}/{addr}/{length}` - 後方互換性対応

### バッチ読み取り
- `POST /api/batch_read` - 複数デバイスを一括読み取り
- `GET /api/batch_read_status` - バッチ読み取り機能の状態確認

## 技術仕様

### MCプロトコル通信
- pymcprotocolライブラリを使用
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