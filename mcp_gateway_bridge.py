"""
MCP Server Gateway - HTTP to MCP Bridge for Copilot Studio
Copilot StudioからのHTTPリクエストをMCPサーバーに橋渡しする
"""

import json
import asyncio
import subprocess
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Gateway Bridge",
    description="HTTP to MCP Protocol Bridge for Copilot Studio Integration",
    version="1.0.0"
)

# CORS設定（Copilot Studio用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では具体的なオリジンを指定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# リクエストモデル
class MCPToolRequest(BaseModel):
    """MCP ツール実行リクエスト"""
    tool: str = Field(..., description="実行するMCPツール名")
    arguments: Dict[str, Any] = Field(default={}, description="ツールの引数")

class PLCReadRequest(BaseModel):
    """PLC読み取りリクエスト（簡易版）"""
    device: str = Field(..., description="デバイス種別（D, M, X, Y等）")
    addr: int = Field(..., description="開始アドレス")
    length: int = Field(1, description="読み取り長さ")

class BatchReadRequest(BaseModel):
    """バッチ読み取りリクエスト"""
    devices: list[str] = Field(..., description="読み取るデバイスリスト")

# MCP通信クラス
class MCPClient:
    """MCPサーバーとの通信を管理"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """MCPツールを実行"""
        try:
            # MCPリクエストを構築
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            # MCPサーバーを起動して通信
            result = await self._communicate_with_mcp(request)
            return result

        except Exception as e:
            logger.error(f"MCP実行エラー: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _communicate_with_mcp(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """MCPサーバーと通信"""
        try:
            # MCPサーバーを子プロセスとして起動
            process = await asyncio.create_subprocess_exec(
                'python', 'mcp_server.py',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # リクエストを送信
            request_str = json.dumps(request) + '\n'
            stdout, stderr = await process.communicate(input=request_str.encode())

            # レスポンスを解析
            if stderr:
                logger.warning(f"MCP stderr: {stderr.decode()}")

            response = json.loads(stdout.decode())

            if "error" in response:
                raise Exception(f"MCPエラー: {response['error']}")

            return response.get("result", {})

        except json.JSONDecodeError as e:
            logger.error(f"JSONパースエラー: {e}")
            raise HTTPException(status_code=500, detail="MCPレスポンス解析エラー")
        except Exception as e:
            logger.error(f"MCP通信エラー: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# MCPクライアントインスタンス
mcp_client = MCPClient()

# エンドポイント定義
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "service": "MCP Gateway Bridge",
        "status": "running",
        "endpoints": {
            "read": "/mcp/read",
            "batch_read": "/mcp/batch_read",
            "execute": "/mcp/execute",
            "tools": "/mcp/tools"
        }
    }

@app.post("/mcp/read")
async def read_plc_device(request: PLCReadRequest):
    """PLCデバイス読み取り（MCPツール経由）"""
    result = await mcp_client.execute_tool(
        "read_plc_device",
        {
            "device": request.device,
            "addr": request.addr,
            "length": request.length
        }
    )
    return result

@app.post("/mcp/batch_read")
async def batch_read_plc(request: BatchReadRequest):
    """複数デバイス一括読み取り（MCPツール経由）"""
    result = await mcp_client.execute_tool(
        "batch_read_plc",
        {"devices": request.devices}
    )
    return result

@app.post("/mcp/execute")
async def execute_mcp_tool(request: MCPToolRequest):
    """汎用MCPツール実行"""
    result = await mcp_client.execute_tool(
        request.tool,
        request.arguments
    )
    return result

@app.get("/mcp/tools")
async def get_available_tools():
    """利用可能なMCPツール一覧取得"""
    result = await mcp_client.execute_tool(
        "get_supported_devices",
        {}
    )

    # 利用可能なツール情報も追加
    return {
        "supported_devices": result,
        "available_tools": [
            "read_plc_device",
            "batch_read_plc",
            "parse_device_spec",
            "get_supported_devices",
            "test_plc_connection",
            "validate_device_spec"
        ]
    }

@app.post("/mcp/test_connection")
async def test_connection():
    """PLC接続テスト"""
    result = await mcp_client.execute_tool(
        "test_plc_connection",
        {}
    )
    return result

# OpenAPI仕様のカスタマイズ
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = app.openapi()
    openapi_schema["info"]["x-logo"] = {
        "url": "https://example.com/logo.png"
    }

    # Copilot Studio用のカスタムフィールド追加
    openapi_schema["info"]["x-ms-connector-metadata"] = [
        {
            "propertyName": "Website",
            "propertyValue": "https://example.com"
        },
        {
            "propertyName": "Privacy policy",
            "propertyValue": "https://example.com/privacy"
        }
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)