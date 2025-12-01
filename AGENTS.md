# Repository Guidelines

## プロジェクト構成とモジュール
- `gateway.py`: FastAPI 本体と REST エンドポイント。
- `main.py`: REST API の統合ランチャー（ローカル/本番起動を切替）。
- `device_readers/`: ワード/ビットデバイスの読み取り戦略クラス。新デバイスタイプはここを拡張。
- `mcprotocol/`: MC プロトコルの低レイヤー（定数、エラー、3E プロトコル、デバイス管理）。
- `plc_operations.py`, `network_utils.py`, `batch_device_reader.py`: PLC IO 共通処理、ネットワーク情報、バッチ読み取り補助。
- バージョン情報: `version.py`。

## ビルド・テスト・開発コマンド
- 依存インストール: `pip install -r requirements.txt`
- 統合起動（ホットリロード有り）: `python main.py`
- 本番モード起動: `python main.py --production`
- ポート変更: `python main.py --port 9000`
- uvicorn 直接起動: `uvicorn gateway:app --reload --host 0.0.0.0 --port 8000`
- 簡易動作確認: REST 起動後 `curl "http://localhost:8000/api/read/D/100/1"`

## コーディングスタイルと命名
- Python 3 / FastAPI。PEP 8 準拠（4 スペース、snake_case、クラスは CapWords）。
- 新規 API は型ヒントを付け、リクエスト/レスポンスは `pydantic` モデルにまとめる。
- ログ/メッセージは日本語主体。外部仕様に影響する変更時はコメント・ドキュメントを更新。

## テスト方針
- 既存の自動テストなし。新規ロジックは `tests/`（pytest 想定）を作成して追加。
- 手動確認: REST 起動→ `/docs` と `/redoc` をチェックし、主要エンドポイントを curl で叩いて応答を確認。
- MC プロトコル変更時はステージング/モックで読み取りを再現し、PLC 接続挙動を確認。

## コミットと PR ガイド
- コミットは短い日本語サマリが慣例。1 行目で変更点を簡潔に。
- PR には変更内容・目的・確認手順（コマンドや curl）を記載。UI/API 変化がある場合はスクリーンショットやレスポンス例を添付。
- 関連課題を紐付け、破壊的変更や新環境変数（`PLC_IP`, `PLC_PORT`, `PLC_TIMEOUT_SEC`）は明記。
