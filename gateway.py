# ------------------------------------------------------------
# gateway.py
# FastAPI Gateway ─ 1810 / 1811 File-API & Device Read
# ------------------------------------------------------------
import os
import re
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mcprotocol import Type3E
from mcprotocol.errors import MCProtocolError
from device_readers.base_device_reader import DeviceReadResult
from version import __version__, format_version_string
from network_utils import print_access_info

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

# FastAPIアプリケーション起動時に実行
if __name__ != "__main__":
    startup_message()

# ──────────────────── FastAPI ────────────────────
app = FastAPI(
    title="PLC Gateway API",
    description="三菱PLCとMCプロトコルで通信するためのGateway API。",
    version=__version__,
    contact={
        "name": "PLC Gateway API開発チーム",
        "url": "https://github.com/your-org/plc-gateway",
        "email": "support@your-org.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
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

        # Pydanticの型検証を確実に通すため dict に変換
        results_payload = [
            r.model_dump() if hasattr(r, "model_dump") else r.dict() if hasattr(r, "dict") else r
            for r in results
        ]
        
        # 成功数カウント
        successful_count = sum(1 for r in results if getattr(r, "success", False))
        
        return BatchReadResponse(
            results=results_payload,  # type: ignore[arg-type]
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


# ──────────────────── 起動時処理 ────────────────────
@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    print("PLC Gateway API を起動中...")
    print(f"PLC接続設定: {PLC_IP}:{PLC_PORT} (timeout: {TIMEOUT_SEC}s)")
    print("PLC Gateway API が正常に起動しました")
