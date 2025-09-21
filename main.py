#!/usr/bin/env python3
"""
PLC Gateway 統合起動スクリプト
==============================

FastAPI REST API、MCPサーバー、または両方を同時に起動する統合スクリプト
"""

import asyncio
import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Optional

import uvicorn

from version import __version__, format_version_string, get_version_info
from network_utils import get_local_ip, get_hostname, print_network_diagnosis


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("plc-gateway-launcher")


class ServiceManager:
    """サービス管理クラス"""

    def __init__(self):
        self.rest_process: Optional[subprocess.Popen] = None
        self.mcp_process: Optional[subprocess.Popen] = None
        self.rest_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()

    def start_rest_api(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
        """
        FastAPI REST APIを起動

        Args:
            host: バインドするホスト
            port: バインドするポート
            reload: ホットリロードを有効にするか
        """
        logger.info(f"🌐 FastAPI REST API を起動中... ({host}:{port})")

        try:
            # uvicornをサブプロセスで起動
            uvicorn_cmd = [
                sys.executable, "-m", "uvicorn", "gateway:app",
                "--host", host,
                "--port", str(port),
                "--log-level", "info"
            ]

            if reload:
                uvicorn_cmd.append("--reload")

            self.rest_process = subprocess.Popen(
                uvicorn_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )

            # 起動確認
            time.sleep(3)

            if self.rest_process.poll() is None:
                logger.info(f"✅ FastAPI REST API が起動しました")

                # アクセス可能なURLを表示
                local_ip = get_local_ip()
                hostname = get_hostname()

                logger.info(f"📚 APIドキュメント:")
                logger.info(f"  - http://localhost:{port}/docs")
                if local_ip != "127.0.0.1":
                    logger.info(f"  - http://{local_ip}:{port}/docs")
                if hostname != "localhost":
                    logger.info(f"  - http://{hostname}:{port}/docs")

                # REST APIのログ出力を監視
                def monitor_rest_logs():
                    while not self.shutdown_event.is_set():
                        try:
                            if self.rest_process and self.rest_process.poll() is None:
                                output = self.rest_process.stderr.readline()
                                if output:
                                    logger.info(f"REST: {output.strip()}")
                            else:
                                break
                        except Exception as e:
                            logger.error(f"RESTログ監視エラー: {e}")
                            break
                        time.sleep(0.1)

                log_thread = threading.Thread(target=monitor_rest_logs, daemon=True)
                log_thread.start()
            else:
                logger.error("REST API の起動に失敗しました")

        except Exception as e:
            logger.error(f"REST API起動エラー: {e}")
            raise

    def start_mcp_server(self):
        """
        MCPサーバーを起動
        """
        logger.info("🔌 MCP サーバーを起動中...")

        try:
            # MCPサーバーをsubprocessで起動
            self.mcp_process = subprocess.Popen(
                [sys.executable, "mcp_server.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=0  # リアルタイム出力のため
            )

            logger.info("✅ MCP サーバーが起動しました")
            logger.info("🔌 MCPクライアントからの接続を待機中...")

            # MCPサーバーのログ出力を監視
            def monitor_mcp_logs():
                while not self.shutdown_event.is_set():
                    try:
                        if self.mcp_process and self.mcp_process.poll() is None:
                            output = self.mcp_process.stderr.readline()
                            if output:
                                logger.info(f"MCP: {output.strip()}")
                        else:
                            break
                    except Exception as e:
                        logger.error(f"MCPログ監視エラー: {e}")
                        break
                    time.sleep(0.1)

            log_thread = threading.Thread(target=monitor_mcp_logs, daemon=True)
            log_thread.start()

        except Exception as e:
            logger.error(f"MCP サーバー起動エラー: {e}")
            raise

    def stop_services(self):
        """
        全サービスを停止
        """
        logger.info("🛑 サービスを停止中...")

        self.shutdown_event.set()

        # REST APIプロセスを停止
        if self.rest_process:
            logger.info("REST API サーバーを停止中...")
            try:
                self.rest_process.terminate()
                self.rest_process.wait(timeout=5)
                logger.info("✅ REST API サーバーを停止しました")
            except subprocess.TimeoutExpired:
                logger.warning("REST API サーバーの強制終了")
                self.rest_process.kill()
            except Exception as e:
                logger.error(f"REST API サーバー停止エラー: {e}")

        # MCPサーバーを停止
        if self.mcp_process:
            logger.info("MCP サーバーを停止中...")
            try:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
                logger.info("✅ MCP サーバーを停止しました")
            except subprocess.TimeoutExpired:
                logger.warning("MCP サーバーの強制終了")
                self.mcp_process.kill()
            except Exception as e:
                logger.error(f"MCP サーバー停止エラー: {e}")

        logger.info("✅ 全サービスが停止しました")

    def wait_for_shutdown(self):
        """
        シャットダウンシグナルを待機
        """
        def signal_handler(signum, frame):
            logger.info(f"シャットダウンシグナル受信: {signum}")
            self.stop_services()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # メインループ（シグナル待機）
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("キーボード割り込み受信")
            self.stop_services()


def print_banner():
    """
    起動時のバナーを表示
    """
    banner = f"""
============================================================
                PLC Gateway 統合起動システム
              FastAPI + OpenAPI + MCP Server
                      Version {__version__:^8}
============================================================
    """
    print(banner)

    # バージョン詳細情報を表示
    print("\n" + "="*60)
    print(format_version_string())
    print("="*60 + "\n")


def print_service_info(args):
    """
    起動するサービスの情報を表示
    """
    version_info = get_version_info()
    logger.info(f"🏷️  バージョン: PLC Gateway v{version_info['plc_gateway_version']}")
    logger.info("📋 起動設定:")

    if args.rest_api:
        # 本番モード時のホスト設定
        host = "0.0.0.0" if args.production else args.host

        # モード表示
        if args.production:
            logger.info("  ⚠️  本番モード: 外部アクセス許可")
        else:
            logger.info("  🔒 開発モード: localhostのみアクセス可能")

        # アクセス可能なURLを取得
        local_ip = get_local_ip()
        hostname = get_hostname()

        logger.info(f"  🌐 FastAPI REST API ({host}):")
        logger.info(f"     - http://localhost:{args.port} (ローカル)")

        if args.production:
            if local_ip != "127.0.0.1":
                logger.info(f"     - http://{local_ip}:{args.port} (IPアドレス)")
            if hostname != "localhost":
                logger.info(f"     - http://{hostname}:{args.port} (ホスト名)")
        else:
            logger.info("     - 外部アクセス: 無効（--productionで有効化）")

        logger.info(f"     - OpenAPI仕様: /docs")
        logger.info(f"     - JSON仕様: /api/openapi/json")
        logger.info(f"     - YAML仕様: /api/openapi/yaml")

    if args.mcp_server:
        logger.info("  🔌 MCP Server: stdio通信")
        logger.info("     - AI統合: MCPクライアント経由でPLCアクセス")

    # 環境変数の表示
    plc_ip = os.getenv("PLC_IP", "127.0.0.1")
    plc_port = os.getenv("PLC_PORT", "5511")
    timeout_sec = os.getenv("PLC_TIMEOUT_SEC", "3.0")
    logger.info(f"  📡 PLC設定: {plc_ip}:{plc_port} (timeout: {timeout_sec}s)")


def main():
    """
    メイン関数
    """
    parser = argparse.ArgumentParser(
        description="PLC Gateway 統合起動システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 開発モード（localhostのみ）
  python main.py --rest-api --mcp-server

  # 本番モード（外部アクセス許可）
  python main.py --rest-api --mcp-server --production

  # REST APIのみ起動
  python main.py --rest-api

  # MCPサーバーのみ起動
  python main.py --mcp-server

  # カスタムポートで起動
  python main.py --rest-api --port 9000

環境変数設定:
  PLC_IP=192.168.1.100          # PLCのIPアドレス
  PLC_PORT=5511                 # PLCのポート番号
  PLC_TIMEOUT_SEC=3.0           # タイムアウト秒数
  MCP_LOG_LEVEL=DEBUG           # MCPログレベル
        """
    )

    parser.add_argument(
        "--rest-api",
        action="store_true",
        help="FastAPI REST APIを起動"
    )

    parser.add_argument(
        "--mcp-server",
        action="store_true",
        help="MCPサーバーを起動"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="REST APIのバインドホスト (デフォルト: 127.0.0.1)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="REST APIのポート番号 (デフォルト: 8000)"
    )

    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="ホットリロードを無効にする"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル (デフォルト: INFO)"
    )

    parser.add_argument(
        "--production",
        action="store_true",
        help="本番モード: 外部からのアクセスを許可 (0.0.0.0でバインド)"
    )

    args = parser.parse_args()

    # 起動オプションの検証
    if not args.rest_api and not args.mcp_server:
        parser.error("--rest-api または --mcp-server のいずれかを指定してください")

    # ログレベル設定
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # バナー表示
    print_banner()

    # サービス情報表示
    print_service_info(args)

    # サービス管理インスタンス
    service_manager = ServiceManager()

    try:
        # FastAPI REST API起動
        if args.rest_api:
            # 本番モード時のホスト設定
            host = "0.0.0.0" if args.production else args.host

            service_manager.start_rest_api(
                host=host,
                port=args.port,
                reload=not args.no_reload
            )

        # MCPサーバー起動
        if args.mcp_server:
            service_manager.start_mcp_server()

        logger.info("🚀 すべてのサービスが正常に起動しました")

        # ネットワーク診断の実行と表示（REST APIが起動している場合）
        if args.rest_api:
            print_network_diagnosis(args.port)

        logger.info("終了するには Ctrl+C を押してください")

        # シャットダウン待機
        service_manager.wait_for_shutdown()

    except KeyboardInterrupt:
        logger.info("キーボード割り込みを受信しました")
    except Exception as e:
        logger.error(f"起動エラー: {e}")
        sys.exit(1)
    finally:
        service_manager.stop_services()


if __name__ == "__main__":
    main()