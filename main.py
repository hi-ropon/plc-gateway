#!/usr/bin/env python3
"""
PLC Gateway 統合起動スクリプト
==============================

FastAPI REST API を起動するためのスクリプト
"""

import asyncio
import argparse
import importlib
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import List, Optional

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
        self.rest_server: Optional["uvicorn.Server"] = None  # type: ignore[name-defined]
        self.rest_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        self.frozen_executable = getattr(sys, "frozen", False)

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
            if self.frozen_executable:
                if reload:
                    logger.warning("PyInstaller実行中はホットリロードを無効化します")

                try:
                    gateway_module = importlib.import_module("gateway")
                    fastapi_app = getattr(gateway_module, "app")
                except Exception as import_error:
                    logger.error(f"FastAPIアプリのロードに失敗しました: {import_error}")
                    raise

                config = uvicorn.Config(
                    fastapi_app,
                    host=host,
                    port=port,
                    log_level="info",
                    reload=False,
                )
                self.rest_server = uvicorn.Server(config)

                def run_server():
                    asyncio.run(self.rest_server.serve())

                self.rest_thread = threading.Thread(target=run_server, daemon=True)
                self.rest_thread.start()

                # 起動確認
                for _ in range(30):
                    if self.rest_server.started:
                        break
                    time.sleep(0.2)
                started = self.rest_server.started
            else:
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
                started = self.rest_process.poll() is None

            if started:
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

                if self.rest_process:
                    # REST APIのログ出力を監視（サブプロセス起動時のみ）
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

    def stop_services(self):
        """
        全サービスを停止
        """
        logger.info("🛑 サービスを停止中...")

        self.shutdown_event.set()

        # REST APIプロセス／スレッドを停止
        if self.rest_process:
            logger.info("REST API サーバー(サブプロセス)を停止中...")
            try:
                self.rest_process.terminate()
                self.rest_process.wait(timeout=5)
                logger.info("✅ REST API サーバーを停止しました")
            except subprocess.TimeoutExpired:
                logger.warning("REST API サーバーの強制終了")
                self.rest_process.kill()
            except Exception as e:
                logger.error(f"REST API サーバー停止エラー: {e}")
        elif self.rest_server:
            logger.info("REST API サーバー(内蔵)を停止中...")
            self.rest_server.should_exit = True
            if self.rest_thread:
                self.rest_thread.join(timeout=5)
            logger.info("✅ REST API サーバーを停止しました")

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
                      FastAPI REST API
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

    # 環境変数の表示
    plc_ip = os.getenv("PLC_IP", "127.0.0.1")
    plc_port = os.getenv("PLC_PORT", "5511")
    timeout_sec = os.getenv("PLC_TIMEOUT_SEC", "3.0")
    plc_transport = os.getenv("PLC_TRANSPORT", "tcp")
    logger.info(f"  📡 PLC設定: {plc_ip}:{plc_port} (timeout: {timeout_sec}s, transport: {plc_transport})")


def build_parser() -> argparse.ArgumentParser:
    """構成済みの引数パーサーを返す"""
    parser = argparse.ArgumentParser(
        description="PLC Gateway 統合起動システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 開発モード（localhostのみ）
  python main.py

  # 本番モード（外部アクセス許可）
  python main.py --production

  # カスタムポートで起動
  python main.py --port 9000

環境変数設定:
  PLC_IP=192.168.1.100          # PLCのIPアドレス
  PLC_PORT=5511                 # PLCのポート番号
  PLC_TIMEOUT_SEC=3.0           # タイムアウト秒数
        """
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

    return parser


def run(argv: Optional[List[str]] = None):
    """引数を指定してランチャーを実行"""
    parser = build_parser()
    args = parser.parse_args(argv)

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
        host = "0.0.0.0" if args.production else args.host
        service_manager.start_rest_api(
            host=host,
            port=args.port,
            reload=not args.no_reload
        )

        logger.info("🚀 すべてのサービスが正常に起動しました")

        # ネットワーク診断の実行と表示（REST APIが起動している場合）
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
    run()
