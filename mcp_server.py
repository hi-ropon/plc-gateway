#!/usr/bin/env python3
"""
MCP Server for PLC Gateway
===========================

Model Context Protocol (MCP) サーバー実装
AI アシスタントがPLCデバイスに直接アクセス可能にします
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

from plc_operations import PLCOperations, PLCConnectionConfig
from version import __version__, format_version_string


# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-plc-gateway")

# 起動時にバージョン情報を表示
def print_version_info():
    """バージョン情報をログに出力"""
    logger.info("="*60)
    logger.info(f"MCP Server for PLC Gateway v{__version__}")
    logger.info("="*60)
    for line in format_version_string().split("\n"):
        logger.info(line)
    logger.info("="*60)

# PLCオペレーションインスタンス
plc_ops = PLCOperations()

# MCPサーバーインスタンス
server = Server("plc-gateway")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """
    利用可能なツールのリストを返す
    """
    return [
        Tool(
            name="read_plc_device",
            description="PLCデバイスから値を読み取ります",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "デバイス種別 (D, M, X, Y, W, R, ZR)"
                    },
                    "address": {
                        "type": "integer",
                        "description": "デバイスアドレス"
                    },
                    "length": {
                        "type": "integer",
                        "description": "読み取り長（デフォルト: 1）",
                        "default": 1
                    },
                    "plc_ip": {
                        "type": "string",
                        "description": "PLCのIPアドレス（省略時は環境変数使用）"
                    },
                    "plc_port": {
                        "type": "integer",
                        "description": "PLCのポート番号（省略時は環境変数使用）"
                    }
                },
                "required": ["device", "address"]
            }
        ),
        Tool(
            name="batch_read_plc",
            description="複数のPLCデバイスを一括で読み取ります",
            inputSchema={
                "type": "object",
                "properties": {
                    "devices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "デバイス指定リスト（例: ['D100', 'M200:3', 'X1A']）"
                    },
                    "plc_ip": {
                        "type": "string",
                        "description": "PLCのIPアドレス（省略時は環境変数使用）"
                    },
                    "plc_port": {
                        "type": "integer",
                        "description": "PLCのポート番号（省略時は環境変数使用）"
                    }
                },
                "required": ["devices"]
            }
        ),
        Tool(
            name="parse_device_spec",
            description="デバイス指定文字列を解析して情報を取得します",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_spec": {
                        "type": "string",
                        "description": "デバイス指定文字列（例: 'D100', 'M200:3', 'X1A'）"
                    }
                },
                "required": ["device_spec"]
            }
        ),
        Tool(
            name="get_supported_devices",
            description="サポートされているPLCデバイス種別のリストを取得します",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="test_plc_connection",
            description="PLC接続をテストして状態を確認します",
            inputSchema={
                "type": "object",
                "properties": {
                    "plc_ip": {
                        "type": "string",
                        "description": "PLCのIPアドレス（省略時は環境変数使用）"
                    },
                    "plc_port": {
                        "type": "integer",
                        "description": "PLCのポート番号（省略時は環境変数使用）"
                    },
                    "timeout_sec": {
                        "type": "number",
                        "description": "タイムアウト秒数（省略時は環境変数使用）"
                    }
                }
            }
        ),
        Tool(
            name="validate_device_spec",
            description="デバイス指定文字列の妥当性をチェックします",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_spec": {
                        "type": "string",
                        "description": "デバイス指定文字列"
                    }
                },
                "required": ["device_spec"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """
    ツール呼び出しを処理
    """
    try:
        if name == "read_plc_device":
            return await _handle_read_plc_device(arguments)
        elif name == "batch_read_plc":
            return await _handle_batch_read_plc(arguments)
        elif name == "parse_device_spec":
            return await _handle_parse_device_spec(arguments)
        elif name == "get_supported_devices":
            return await _handle_get_supported_devices(arguments)
        elif name == "test_plc_connection":
            return await _handle_test_plc_connection(arguments)
        elif name == "validate_device_spec":
            return await _handle_validate_device_spec(arguments)
        else:
            return [TextContent(
                type="text",
                text=f"未知のツール: {name}"
            )]
    except Exception as e:
        logger.error(f"ツール実行エラー {name}: {e}")
        return [TextContent(
            type="text",
            text=f"エラーが発生しました: {str(e)}"
        )]


async def _handle_read_plc_device(arguments: Dict[str, Any]) -> List[TextContent]:
    """単一デバイス読み取りツールの処理"""
    device = arguments["device"]
    address = arguments["address"]
    length = arguments.get("length", 1)
    plc_ip = arguments.get("plc_ip")
    plc_port = arguments.get("plc_port")

    config = PLCConnectionConfig(ip=plc_ip, port=plc_port)

    try:
        values = plc_ops.read_single_device(device, address, length, config)

        result = {
            "success": True,
            "device": device,
            "address": address,
            "length": length,
            "values": values,
            "plc_config": str(config)
        }

        return [TextContent(
            type="text",
            text=f"📊 PLC読み取り成功\n\n"
                 f"デバイス: {device}{address}\n"
                 f"読み取り長: {length}\n"
                 f"値: {values}\n"
                 f"接続先: {config}\n\n"
                 f"詳細:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
        )]

    except Exception as e:
        error_result = {
            "success": False,
            "device": device,
            "address": address,
            "length": length,
            "error": str(e),
            "plc_config": str(config)
        }

        return [TextContent(
            type="text",
            text=f"❌ PLC読み取りエラー\n\n"
                 f"デバイス: {device}{address}\n"
                 f"エラー: {str(e)}\n"
                 f"接続先: {config}\n\n"
                 f"詳細:\n```json\n{json.dumps(error_result, indent=2, ensure_ascii=False)}\n```"
        )]


async def _handle_batch_read_plc(arguments: Dict[str, Any]) -> List[TextContent]:
    """バッチ読み取りツールの処理"""
    devices = arguments["devices"]
    plc_ip = arguments.get("plc_ip")
    plc_port = arguments.get("plc_port")

    config = PLCConnectionConfig(ip=plc_ip, port=plc_port)

    try:
        results = plc_ops.batch_read_devices(devices, config)

        # 結果をサマリー形式で整理
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count

        summary = {
            "total_devices": len(devices),
            "successful_devices": successful_count,
            "failed_devices": failed_count,
            "plc_config": str(config),
            "results": [
                {
                    "device": r.device,
                    "success": r.success,
                    "values": r.values if r.success else None,
                    "error": r.error if not r.success else None
                }
                for r in results
            ]
        }

        # 成功/失敗の詳細を文字列で作成
        success_details = []
        error_details = []

        for result in results:
            if result.success:
                success_details.append(f"  ✅ {result.device}: {result.values}")
            else:
                error_details.append(f"  ❌ {result.device}: {result.error}")

        response_text = f"📊 PLCバッチ読み取り結果\n\n"
        response_text += f"総デバイス数: {len(devices)}\n"
        response_text += f"成功: {successful_count}, 失敗: {failed_count}\n"
        response_text += f"接続先: {config}\n\n"

        if success_details:
            response_text += "**成功したデバイス:**\n" + "\n".join(success_details) + "\n\n"

        if error_details:
            response_text += "**失敗したデバイス:**\n" + "\n".join(error_details) + "\n\n"

        response_text += f"詳細:\n```json\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n```"

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        error_result = {
            "total_devices": len(devices),
            "successful_devices": 0,
            "failed_devices": len(devices),
            "error": str(e),
            "plc_config": str(config)
        }

        return [TextContent(
            type="text",
            text=f"❌ PLCバッチ読み取りエラー\n\n"
                 f"対象デバイス: {devices}\n"
                 f"エラー: {str(e)}\n"
                 f"接続先: {config}\n\n"
                 f"詳細:\n```json\n{json.dumps(error_result, indent=2, ensure_ascii=False)}\n```"
        )]


async def _handle_parse_device_spec(arguments: Dict[str, Any]) -> List[TextContent]:
    """デバイス指定解析ツールの処理"""
    device_spec = arguments["device_spec"]

    try:
        device_type, address, length = plc_ops.parse_device_spec(device_spec)

        result = {
            "device_spec": device_spec,
            "parsed": {
                "device_type": device_type,
                "address": address,
                "address_hex": f"0x{address:X}",
                "length": length
            },
            "is_valid": True
        }

        return [TextContent(
            type="text",
            text=f"🔍 デバイス指定解析結果\n\n"
                 f"入力: `{device_spec}`\n"
                 f"デバイス種別: {device_type}\n"
                 f"アドレス: {address} (0x{address:X})\n"
                 f"読み取り長: {length}\n\n"
                 f"詳細:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
        )]

    except Exception as e:
        error_result = {
            "device_spec": device_spec,
            "is_valid": False,
            "error": str(e)
        }

        return [TextContent(
            type="text",
            text=f"❌ デバイス指定解析エラー\n\n"
                 f"入力: `{device_spec}`\n"
                 f"エラー: {str(e)}\n\n"
                 f"詳細:\n```json\n{json.dumps(error_result, indent=2, ensure_ascii=False)}\n```"
        )]


async def _handle_get_supported_devices(arguments: Dict[str, Any]) -> List[TextContent]:
    """サポートデバイス取得ツールの処理"""
    supported_devices = plc_ops.get_supported_devices()

    result = {
        "supported_devices": supported_devices,
        "device_descriptions": {
            "D": "データレジスタ（ワードデバイス）",
            "W": "リンクレジスタ（ワードデバイス）",
            "R": "ファイルレジスタ（ワードデバイス）",
            "ZR": "インデックスレジスタ（ワードデバイス）",
            "X": "入力リレー（ビットデバイス、16進アドレス）",
            "Y": "出力リレー（ビットデバイス、16進アドレス）",
            "M": "内部リレー（ビットデバイス、10進アドレス）"
        },
        "format_examples": [
            "D100 (単一デバイス)",
            "D100:5 (連続5個読み取り)",
            "X1A (16進アドレス)",
            "M0x10 (16進プレフィックス付き)",
            "YH20 (16進 H記法)"
        ]
    }

    response_text = "📋 サポートされているPLCデバイス\n\n"
    response_text += "**デバイス種別:**\n"
    for device in supported_devices:
        desc = result["device_descriptions"].get(device, "")
        response_text += f"  • {device}: {desc}\n"

    response_text += "\n**指定形式の例:**\n"
    for example in result["format_examples"]:
        response_text += f"  • {example}\n"

    response_text += f"\n詳細:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"

    return [TextContent(type="text", text=response_text)]


async def _handle_test_plc_connection(arguments: Dict[str, Any]) -> List[TextContent]:
    """PLC接続テストツールの処理"""
    plc_ip = arguments.get("plc_ip")
    plc_port = arguments.get("plc_port")
    timeout_sec = arguments.get("timeout_sec")

    config = PLCConnectionConfig(ip=plc_ip, port=plc_port, timeout_sec=timeout_sec)

    result = plc_ops.test_connection(config)

    if result["connected"]:
        status_icon = "✅"
        status_text = "接続成功"
    else:
        status_icon = "❌"
        status_text = "接続失敗"

    response_text = f"{status_icon} PLC接続テスト結果\n\n"
    response_text += f"接続先: {result['config']}\n"
    response_text += f"状態: {status_text}\n"

    if result["connected"]:
        response_text += f"応答時間: {result['response_time_ms']}ms\n"
        if result.get("test_read_value") is not None:
            response_text += f"テスト読み取り値 (D0): {result['test_read_value']}\n"
    else:
        response_text += f"エラー: {result['error']}\n"

    response_text += f"\n詳細:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"

    return [TextContent(type="text", text=response_text)]


async def _handle_validate_device_spec(arguments: Dict[str, Any]) -> List[TextContent]:
    """デバイス指定妥当性チェックツールの処理"""
    device_spec = arguments["device_spec"]

    is_valid = plc_ops.validate_device_spec(device_spec)

    result = {
        "device_spec": device_spec,
        "is_valid": is_valid
    }

    if is_valid:
        try:
            device_type, address, length = plc_ops.parse_device_spec(device_spec)
            result["parsed_info"] = {
                "device_type": device_type,
                "address": address,
                "length": length
            }
        except:
            pass

    status_icon = "✅" if is_valid else "❌"
    status_text = "有効" if is_valid else "無効"

    response_text = f"{status_icon} デバイス指定妥当性チェック\n\n"
    response_text += f"入力: `{device_spec}`\n"
    response_text += f"結果: {status_text}\n"

    if is_valid and "parsed_info" in result:
        info = result["parsed_info"]
        response_text += f"デバイス種別: {info['device_type']}\n"
        response_text += f"アドレス: {info['address']}\n"
        response_text += f"読み取り長: {info['length']}\n"

    response_text += f"\n詳細:\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"

    return [TextContent(type="text", text=response_text)]


async def main():
    """
    MCPサーバーのメイン関数
    """
    print_version_info()
    logger.info("🚀 PLC Gateway MCP サーバーを起動中...")

    # 環境変数から設定を読み込み
    plc_ip = os.getenv("PLC_IP", "127.0.0.1")
    plc_port = os.getenv("PLC_PORT", "5511")
    timeout_sec = os.getenv("PLC_TIMEOUT_SEC", "3.0")

    logger.info(f"📡 PLC設定: {plc_ip}:{plc_port} (timeout: {timeout_sec}s)")
    logger.info("✅ PLC Gateway MCP サーバーが準備完了")
    logger.info("🔌 MCPクライアントからの接続を待機中...")

    # stdio経由でMCPサーバーを実行
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="plc-gateway",
                server_version="1.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                )
            )
        )


if __name__ == "__main__":
    # ログレベルを環境変数から設定
    log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    asyncio.run(main())