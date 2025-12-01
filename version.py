"""
PLC Gateway バージョン情報
==========================

プロジェクト全体のバージョン情報を管理
"""

# バージョン情報
__version__ = "1.2.0"
__release_date__ = "2025-01-20"
__author__ = "PLC Gateway Development Team"

# コンポーネントバージョン
COMPONENT_VERSIONS = {
    "rest_api": "1.2.0",
    "plc_operations": "1.1.0",
    "batch_reader": "1.0.0"
}

# 機能リリース情報
FEATURES = {
    "1.2.0": [
        "バージョン表示機能追加",
        "統合起動システム改善"
    ],
    "1.1.0": [
        "バッチ読み取り機能追加",
        "デバイスリーダー戦略パターン実装"
    ],
    "1.0.0": [
        "初期リリース",
        "基本的なPLCデバイス読み取り"
    ]
}

def get_version_info() -> dict:
    """
    詳細なバージョン情報を取得

    Returns:
        dict: バージョン情報の辞書
    """
    import sys
    import platform

    # 依存ライブラリのバージョンを取得
    lib_versions = {}

    try:
        import fastapi
        lib_versions["fastapi"] = fastapi.__version__
    except ImportError:
        lib_versions["fastapi"] = "未インストール"

    try:
        import mcprotocol
        lib_versions["mcprotocol"] = mcprotocol.__version__
    except ImportError:
        lib_versions["mcprotocol"] = "未インストール"

    try:
        import uvicorn
        lib_versions["uvicorn"] = uvicorn.__version__
    except ImportError:
        lib_versions["uvicorn"] = "未インストール"

    return {
        "plc_gateway_version": __version__,
        "release_date": __release_date__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "components": COMPONENT_VERSIONS,
        "libraries": lib_versions,
        "latest_features": FEATURES.get(__version__, [])
    }

def format_version_string() -> str:
    """
    フォーマット済みのバージョン文字列を生成

    Returns:
        str: バージョン表示用文字列
    """
    info = get_version_info()

    lines = []
    lines.append(f"PLC Gateway v{info['plc_gateway_version']} ({info['release_date']})")
    lines.append(f"Python {info['python_version']} on {info['platform']}")
    lines.append("")
    lines.append("コンポーネント:")
    for comp, ver in info['components'].items():
        lines.append(f"  - {comp}: v{ver}")
    lines.append("")
    lines.append("依存ライブラリ:")
    for lib, ver in info['libraries'].items():
        lines.append(f"  - {lib}: {ver}")

    return "\n".join(lines)

if __name__ == "__main__":
    # 直接実行時はバージョン情報を表示
    print(format_version_string())
