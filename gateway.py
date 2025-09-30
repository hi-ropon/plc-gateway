# ------------------------------------------------------------
# gateway.py
# FastAPI Gateway ─ 1810 / 1811 File-API & Device Read
# ------------------------------------------------------------
import os
import json
import yaml
import base64
import re
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Response, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from mcprotocol import Type3E
from mcprotocol.errors import MCProtocolError
from device_readers.base_device_reader import DeviceReadResult
from version import __version__, format_version_string
from network_utils import get_local_ip, get_hostname, get_openapi_servers, print_access_info

# ──────────────────── 環境変数 ────────────────────
PLC_IP      = os.getenv("PLC_IP",         "127.0.0.1")
PLC_PORT    = int(os.getenv("PLC_PORT",   "5511"))
TIMEOUT_SEC = float(os.getenv("PLC_TIMEOUT_SEC", "3.0"))

# 起動時にバージョン情報を表示
def startup_message():
    """起動時のメッセージを表示"""
    print("\n" + "="*60)
    print(f"  PLC Gateway REST API v{__version__}")
    print("="*60)
    print(format_version_string())
    print("="*60)
    print(f"\nFastAPI REST API 起動")
    print(f"  PLC接続設定: {PLC_IP}:{PLC_PORT} (timeout: {TIMEOUT_SEC}s)")

    # アクセス情報を表示
    print_access_info(port=8000)

    # API仕様ファイル
    local_ip = get_local_ip()
    hostname = get_hostname()

    print("APIドキュメント:")
    print(f"  - http://localhost:8000/docs")
    if local_ip != "127.0.0.1":
        print(f"  - http://{local_ip}:8000/docs")
    if hostname != "localhost":
        print(f"  - http://{hostname}:8000/docs")

    print("\nOpenAPI仕様:")
    print(f"  - http://localhost:8000/api/openapi/json")
    print(f"  - http://localhost:8000/api/openapi/yaml\n")

# FastAPIアプリケーション起動時に実行
if __name__ != "__main__":
    startup_message()

# ──────────────────── FastAPI ────────────────────
app = FastAPI(
    title="PLC Gateway API",
    description="三菱PLCとMCプロトコルで通信するためのGateway API。Copilot Studioなどの外部ツールやMCPクライアントから利用可能です。",
    version=__version__,
    contact={
        "name": "PLC Gateway API開発チーム",
        "url": "https://github.com/your-org/plc-gateway",
        "email": "support@your-org.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    servers=get_openapi_servers(port=8000),
    openapi_tags=[
        {
            "name": "Device Read",
            "description": "PLCデバイス読み取り操作"
        },
        {
            "name": "Batch Operations",
            "description": "バッチ読み取り操作"
        },
        {
            "name": "System Status",
            "description": "システム状態確認"
        },
        {
            "name": "OpenAPI Schema",
            "description": "OpenAPI仕様ファイルの取得"
        }
    ]
)

# ──────────────────── CORS設定 ────────────────────
# Copilot Studioなどの外部ツールからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では特定のオリジンに制限することを推奨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ReadRequest(BaseModel):
    device: str = "D"
    addr:   int
    length: int
    plc_host: Optional[str] = None  # コンピューター名またはIPアドレス
    ip:       Optional[str] = None  # 後方互換性のため残す
    port:     Optional[int] = None


class BatchReadRequest(BaseModel):
    devices: List[str]  # 例: ["D100", "D200:5", "M10", "X30", "Y1A"]
    plc_host: Optional[str] = None  # コンピューター名またはIPアドレス
    ip:       Optional[str] = None  # 後方互換性のため残す
    port:     Optional[int] = None


class BatchReadResponse(BaseModel):
    results: List[DeviceReadResult]
    total_devices: int
    successful_devices: int


class ReadResponse(BaseModel):
    """PLCデバイス読み取りレスポンス"""
    values: List[int]


def _parse_device_spec(device_spec: str) -> tuple[str, int, int]:
    """
    デバイス指定文字列を解析
    
    Args:
        device_spec: "D100", "D200:5", "M10", "X1A" 等
        
    Returns:
        tuple: (device_type, address, length)
    """
    # デバイス:長さ の形式をチェック
    if ":" in device_spec:
        device_part, length_str = device_spec.split(":", 1)
        length = int(length_str)
    else:
        device_part = device_spec
        length = 1
    
    # デバイス種別とアドレスを抽出（H記法対応）
    if device_part.upper().find("H") > 0:  # H記法の場合（例: YH20）
        h_pos = device_part.upper().find("H")
        device_type = device_part[:h_pos].upper()
        address_str = device_part[h_pos+1:]  # H以降がアドレス
    else:
        match = re.match(r"^([A-Za-z]+)(.+)$", device_part)
        if not match:
            raise ValueError(f"Invalid device specification: {device_spec}")
        device_type = match.group(1).upper()
        address_str = match.group(2)
    
    # 16進数アドレスの処理（XやYでよく使用）
    if address_str.startswith("0x") or address_str.startswith("0X"):
        address = int(address_str, 16)
    elif device_part.upper().find("H") > 0:  # H記法の場合
        address = int(address_str, 16)
    else:
        # 10進数またはそのまま16進数として解釈を試行
        try:
            address = int(address_str, 10)
        except ValueError:
            try:
                address = int(address_str, 16)
            except ValueError:
                raise ValueError(f"Invalid address format: {address_str}")
    
    return device_type, address, length


def _read_plc(device: str, addr: int, length: int, *, ip: str, port: int) -> List[int]:
    plc = Type3E(plctype="iQ-R")
    plc.setaccessopt(commtype="binary")
    plc.timer = int(TIMEOUT_SEC * 4)
    plc.connect(ip, port)
    try:
        upper = device.upper()
        if upper in ("D", "W", "R", "ZR"):
            return plc.batchread_wordunits(f"{upper}{addr}", length)
        if upper in ("X", "Y", "M"):
            return plc.batchread_bitunits(f"{upper}{addr}", length)
        raise ValueError(f"Unsupported device '{device}'")
    finally:
        plc.close()


def _batch_read_plc(device_specs: List[str], *, ip: str, port: int) -> List[DeviceReadResult]:
    """
    複数デバイスを効率的にバッチ読み取り（Strategy Pattern使用）
    
    Args:
        device_specs: デバイス指定リスト ["D100", "M200", "X30:3"]
        ip: PLC IPアドレス
        port: PLC ポート番号
        
    Returns:
        List[DeviceReadResult]: 読み取り結果リスト
    """
    # モジュールキャッシュ問題の解決：強制再読み込み
    import sys
    import importlib
    
    modules_to_reload = [
        'batch_device_reader',
        'device_readers.base_device_reader',
        'device_readers.bit_device_reader',
        'device_readers.word_device_reader'
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
    
    from batch_device_reader import BatchDeviceReader
    
    if not device_specs:
        return []
    
    # PLC接続
    plc = Type3E(plctype="iQ-R")
    plc.setaccessopt(commtype="binary")
    plc.timer = int(TIMEOUT_SEC * 4)
    
    try:
        plc.connect(ip, port)
        
        # Strategy Patternを使用したバッチ読み取り
        batch_reader = BatchDeviceReader()
        results = batch_reader.batch_read_devices(plc, device_specs)
        
        return results
        
    except Exception as e:
        # PLC接続エラー時は全デバイスエラー扱い
        results = []
        for device_spec in device_specs:
            results.append(DeviceReadResult(
                device=device_spec,
                values=[],
                success=False,
                error=f"PLC connection error: {str(e)}"
            ))
        return results
    finally:
        plc.close()


@app.post("/api/read", tags=["Device Read"],
          response_model=ReadResponse,
          operation_id="read_device",
          summary="単一デバイス読み取り",
          description="指定したPLCデバイスから値を読み取ります")
def api_read(req: ReadRequest):
    try:
        # plc_hostまたはipを使用（plc_hostが優先）
        host = req.plc_host or req.ip or PLC_IP
        vals = _read_plc(req.device, req.addr, req.length,
                         ip=host,
                         port=req.port or PLC_PORT)
        return {"values": vals}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/read/{device}/{addr}/{length}", tags=["Device Read"],
         response_model=ReadResponse,
         operation_id="read_device_get",
         summary="単一デバイス読み取り (GET)",
         description="URLパスパラメータを使用してPLCデバイスから値を読み取ります")
def api_read_get(
    device: str = Path(..., description="デバイス種別（D, W, R, ZR, X, Y, M）"),
    addr: int = Path(..., description="デバイスアドレス（10進数または16進数）"),
    length: int = Path(..., description="読み取り長（ワード数またはビット数）"),
    plc_host: Optional[str] = Query(None, description="PLCのコンピューター名またはIPアドレス（省略時は環境変数使用）"),
    ip: Optional[str] = Query(None, description="PLCのIPアドレス（後方互換性のため残存、plc_hostを推奨）"),
    port: Optional[int] = Query(None, description="PLCのポート番号（省略時は環境変数使用）")
):
    return api_read(ReadRequest(device=device, addr=addr, length=length,
                                plc_host=plc_host, ip=ip, port=port))


# 後方互換性のため、/api/プレフィックスなしでもアクセス可能にする
@app.get("/{device}/{addr}/{length}",
         response_model=ReadResponse,
         operation_id="read_device_compat")
def api_read_get_compat(
    device: str = Path(..., description="デバイス種別（D, W, R, ZR, X, Y, M）"),
    addr: int = Path(..., description="デバイスアドレス（10進数または16進数）"),
    length: int = Path(..., description="読み取り長（ワード数またはビット数）"),
    plc_host: Optional[str] = Query(None, description="PLCのコンピューター名またはIPアドレス（省略時は環境変数使用）"),
    ip: Optional[str] = Query(None, description="PLCのIPアドレス（後方互換性のため残存、plc_hostを推奨）"),
    port: Optional[int] = Query(None, description="PLCのポート番号（省略時は環境変数使用）")
):
    """後方互換性のため、/api/プレフィックスなしでもアクセス可能"""
    return api_read(ReadRequest(device=device, addr=addr, length=length,
                                plc_host=plc_host, ip=ip, port=port))


@app.post("/api/batch_read", response_model=BatchReadResponse,
          tags=["Batch Operations"],
          operation_id="batch_read_devices",
          summary="複数デバイス一括読み取り",
          description="複数のPLCデバイスを一括で読み取ります。MCプロトコルのrandomread機能を活用した効率的な読み取りを行います。")
def api_batch_read(req: BatchReadRequest):
    """
    複数デバイスを一括読み取り

    MCプロトコルのrandomread機能を活用して効率的に読み取り
    """
    try:
        if not req.devices:
            return BatchReadResponse(
                results=[],
                total_devices=0,
                successful_devices=0
            )
        
        # バッチ読み取り実行（plc_hostまたはipを使用）
        host = req.plc_host or req.ip or PLC_IP
        results = _batch_read_plc(
            req.devices,
            ip=host,
            port=req.port or PLC_PORT
        )
        
        # 成功数カウント
        successful_count = sum(1 for r in results if r.success)
        
        return BatchReadResponse(
            results=results,
            total_devices=len(req.devices),
            successful_devices=successful_count
        )
        
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/batch_read_status", tags=["System Status"],
         summary="バッチ読み取り機能の状態確認",
         description="バッチ読み取り機能のサポート状況と制限事項を取得します")
def api_batch_read_status():
    """
    バッチ読み取り機能の状態とサポート情報を取得
    """
    return {
        "batch_read_available": True,
        "supported_devices": ["D", "W", "R", "ZR", "X", "Y", "M"],
        "supported_formats": [
            "D100 (単一デバイス)",
            "D100:5 (連続5個)",
            "X1A (16進数アドレス)",
            "M0x10 (16進数プレフィックス)",
            "YH20 (16進数 H記法)"
        ],
        "max_devices_per_request": 32,  # MCプロトコル制限を考慮
        "randomread_fallback": True,
        "version": "1.0"
    }


# ──────────────────── OpenAPI仕様ファイル出力 ────────────────────
def _convert_openapi_to_swagger2(openapi_schema: dict) -> dict:
    """
    OpenAPI 3.x を Swagger 2.0 に変換

    Args:
        openapi_schema: OpenAPI 3.x 仕様

    Returns:
        dict: Swagger 2.0 仕様
    """
    swagger = {
        "swagger": "2.0",
        "info": openapi_schema.get("info", {}),
        "paths": {},
        "definitions": {},
        "tags": openapi_schema.get("tags", [])
    }

    # serversをhost/basePath/schemesに変換
    servers = openapi_schema.get("servers", [])
    if servers:
        first_server = servers[0]
        url = first_server.get("url", "http://localhost:8000")

        # URLを解析
        import re
        match = re.match(r"^(https?)://([^:/]+)(?::(\d+))?(/.*)?$", url)
        if match:
            scheme = match.group(1)
            host = match.group(2)
            port = match.group(3)
            base_path = match.group(4) or ""

            swagger["schemes"] = [scheme]
            swagger["host"] = f"{host}:{port}" if port else host
            swagger["basePath"] = base_path

    # pathsを変換
    for path, path_item in openapi_schema.get("paths", {}).items():
        swagger["paths"][path] = {}

        for method, operation in path_item.items():
            if method not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue

            swagger_operation = {
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "operationId": operation.get("operationId", f"{method}_{path}"),
                "tags": operation.get("tags", []),
                "produces": ["application/json"],
                "responses": {}
            }

            # parametersを変換
            parameters = []

            # path/query parameters
            for param in operation.get("parameters", []):
                swagger_param = {
                    "name": param.get("name"),
                    "in": param.get("in"),
                    "required": param.get("required", False),
                    "description": param.get("description", "")
                }

                # schemaからtypeを抽出
                schema = param.get("schema", {})
                if "anyOf" in schema:
                    # anyOf の最初の型を使用
                    first_type = schema["anyOf"][0] if schema["anyOf"] else {}
                    swagger_param["type"] = first_type.get("type", "string")
                else:
                    swagger_param["type"] = schema.get("type", "string")
                    if swagger_param["type"] == "integer":
                        swagger_param["format"] = schema.get("format", "int32")

                parameters.append(swagger_param)

            # requestBodyをbody parameterに変換
            if "requestBody" in operation:
                request_body = operation["requestBody"]
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                schema_ref = json_content.get("schema", {})

                body_param = {
                    "name": "body",
                    "in": "body",
                    "required": request_body.get("required", False),
                    "schema": schema_ref
                }
                parameters.append(body_param)
                swagger_operation["consumes"] = ["application/json"]

            if parameters:
                swagger_operation["parameters"] = parameters

            # responsesを変換
            for status_code, response in operation.get("responses", {}).items():
                swagger_response = {
                    "description": response.get("description", "")
                }

                content = response.get("content", {})
                json_content = content.get("application/json", {})
                if "schema" in json_content:
                    swagger_response["schema"] = json_content["schema"]

                swagger_operation["responses"][status_code] = swagger_response

            swagger["paths"][path][method] = swagger_operation

    # components/schemas を definitions に変換
    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})

    for schema_name, schema_def in schemas.items():
        swagger["definitions"][schema_name] = schema_def

    return swagger


def _generate_openapi_files():
    """
    起動時にOpenAPI仕様ファイル（JSON/YAML）とSwagger 2.0仕様を生成
    """
    try:
        # OpenAPI 3.x仕様を取得
        openapi_schema = app.openapi()

        # OpenAPI 3.x - JSON形式で保存
        with open("openapi.json", "w", encoding="utf-8") as f:
            json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

        # OpenAPI 3.x - YAML形式で保存
        with open("openapi.yaml", "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, default_flow_style=False,
                     allow_unicode=True, sort_keys=False)

        # Swagger 2.0に変換
        swagger_schema = _convert_openapi_to_swagger2(openapi_schema)

        # Swagger 2.0 - JSON形式で保存
        with open("swagger.json", "w", encoding="utf-8") as f:
            json.dump(swagger_schema, f, indent=2, ensure_ascii=False)

        # Swagger 2.0 - YAML形式で保存
        with open("swagger.yaml", "w", encoding="utf-8") as f:
            yaml.dump(swagger_schema, f, default_flow_style=False,
                     allow_unicode=True, sort_keys=False)

        print("OpenAPI仕様ファイルを生成しました:")
        print("  - openapi.json, openapi.yaml (OpenAPI 3.1)")
        print("  - swagger.json, swagger.yaml (Swagger 2.0 - Copilot Studio用)")

    except Exception as e:
        print(f"OpenAPI仕様ファイル生成エラー: {e}")


@app.get("/api/openapi/json", tags=["OpenAPI Schema"],
         summary="OpenAPI仕様ファイル（JSON）のダウンロード",
         description="OpenAPI仕様をJSON形式でダウンロードします")
def download_openapi_json():
    """OpenAPI仕様ファイル（JSON）をダウンロード"""
    try:
        openapi_schema = app.openapi()
        return JSONResponse(
            content=openapi_schema,
            headers={
                "Content-Disposition": "attachment; filename=openapi.json",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAPI JSON生成エラー: {str(e)}")


@app.get("/api/openapi/yaml", tags=["OpenAPI Schema"],
         summary="OpenAPI仕様ファイル（YAML）のダウンロード",
         description="OpenAPI仕様をYAML形式でダウンロードします")
def download_openapi_yaml():
    """OpenAPI仕様ファイル（YAML）をダウンロード"""
    try:
        openapi_schema = app.openapi()
        yaml_content = yaml.dump(openapi_schema, default_flow_style=False,
                                allow_unicode=True, sort_keys=False)

        return PlainTextResponse(
            content=yaml_content,
            headers={
                "Content-Disposition": "attachment; filename=openapi.yaml",
                "Content-Type": "application/x-yaml"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAPI YAML生成エラー: {str(e)}")


@app.get("/api/openapi/swagger", tags=["OpenAPI Schema"],
         summary="Swagger 2.0仕様ファイル（JSON）のダウンロード",
         description="Swagger 2.0仕様をJSON形式でダウンロードします（Copilot Studio用）")
def download_swagger_json():
    """Swagger 2.0仕様ファイル（JSON）をダウンロード"""
    try:
        openapi_schema = app.openapi()
        swagger_schema = _convert_openapi_to_swagger2(openapi_schema)

        return JSONResponse(
            content=swagger_schema,
            headers={
                "Content-Disposition": "attachment; filename=swagger.json",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Swagger 2.0 JSON生成エラー: {str(e)}")


@app.get("/api/openapi/swagger/yaml", tags=["OpenAPI Schema"],
         summary="Swagger 2.0仕様ファイル（YAML）のダウンロード",
         description="Swagger 2.0仕様をYAML形式でダウンロードします（Copilot Studio用）")
def download_swagger_yaml():
    """Swagger 2.0仕様ファイル（YAML）をダウンロード"""
    try:
        openapi_schema = app.openapi()
        swagger_schema = _convert_openapi_to_swagger2(openapi_schema)
        yaml_content = yaml.dump(swagger_schema, default_flow_style=False,
                                allow_unicode=True, sort_keys=False)

        return PlainTextResponse(
            content=yaml_content,
            headers={
                "Content-Disposition": "attachment; filename=swagger.yaml",
                "Content-Type": "application/x-yaml"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Swagger 2.0 YAML生成エラー: {str(e)}")


@app.get("/api/openapi/status", tags=["OpenAPI Schema"],
         summary="OpenAPI仕様生成機能の状態確認",
         description="OpenAPI仕様ファイル生成機能の状態とサポート情報を取得します")
def api_openapi_status():
    """
    OpenAPI仕様生成機能の状態確認
    """
    import os

    json_exists = os.path.exists("openapi.json")
    yaml_exists = os.path.exists("openapi.yaml")
    swagger_json_exists = os.path.exists("swagger.json")
    swagger_yaml_exists = os.path.exists("swagger.yaml")

    return {
        "openapi_generation_available": True,
        "file_generation_status": {
            "openapi_json_exists": json_exists,
            "openapi_yaml_exists": yaml_exists,
            "swagger_json_exists": swagger_json_exists,
            "swagger_yaml_exists": swagger_yaml_exists,
            "auto_generation_on_startup": True
        },
        "supported_formats": {
            "openapi_3_1": ["JSON", "YAML"],
            "swagger_2_0": ["JSON", "YAML"]
        },
        "download_endpoints": {
            "openapi_json": "/api/openapi/json",
            "openapi_yaml": "/api/openapi/yaml",
            "swagger_json": "/api/openapi/swagger",
            "swagger_yaml": "/api/openapi/swagger/yaml"
        },
        "copilot_studio_recommendation": "swagger_json または swagger_yaml を使用してください",
        "version": "1.2.0"
    }


# ──────────────────── 起動時処理 ────────────────────
@app.on_event("startup")
async def startup_event():
    """
    アプリケーション起動時の処理
    """
    print("PLC Gateway API を起動中...")
    print(f"PLC接続設定: {PLC_IP}:{PLC_PORT} (timeout: {TIMEOUT_SEC}s)")

    # OpenAPI仕様ファイルを生成
    _generate_openapi_files()

    print("PLC Gateway API が正常に起動しました")

    # アクセス可能なURLを表示
    local_ip = get_local_ip()
    hostname = get_hostname()

    print("\nアクセス可能なURL:")
    print(f"  - http://localhost:8000/docs (ローカル)")
    if local_ip != "127.0.0.1":
        print(f"  - http://{local_ip}:8000/docs (IPアドレス)")
    if hostname != "localhost":
        print(f"  - http://{hostname}:8000/docs (ホスト名)")