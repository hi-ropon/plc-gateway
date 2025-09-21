"""
ネットワークユーティリティ
==========================

サーバーのIPアドレスとホスト名を取得する共通関数
"""

import socket
import logging

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """
    ローカルIPアドレスを取得

    Returns:
        str: ローカルIPアドレス（取得失敗時は127.0.0.1を返す）
    """
    try:
        # 外部への接続を試みることで、使用されるローカルIPを取得
        # 実際には接続しない（UDP）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Googleの公開DNSサーバーに接続を試みる（実際には接続しない）
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception as e:
        logger.warning(f"IPアドレス取得失敗: {e}")
        return "127.0.0.1"


def get_hostname() -> str:
    """
    ホスト名を取得

    Returns:
        str: ホスト名（取得失敗時はlocalhostを返す）
    """
    try:
        hostname = socket.gethostname()
        return hostname
    except Exception as e:
        logger.warning(f"ホスト名取得失敗: {e}")
        return "localhost"


def get_server_urls(port: int = 8000, include_localhost: bool = True) -> list:
    """
    サーバーアクセス用のURLリストを生成

    Args:
        port: サーバーポート番号
        include_localhost: localhostを含めるか

    Returns:
        list: アクセス可能なURLのリスト
    """
    urls = []

    if include_localhost:
        urls.append(f"http://localhost:{port}")

    # IPアドレスでのアクセス
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        urls.append(f"http://{local_ip}:{port}")

    # ホスト名でのアクセス
    hostname = get_hostname()
    if hostname != "localhost":
        urls.append(f"http://{hostname}:{port}")

    return urls


def get_openapi_servers(port: int = 8000) -> list:
    """
    OpenAPI仕様用のサーバー定義リストを生成

    Args:
        port: サーバーポート番号

    Returns:
        list: OpenAPIサーバー定義のリスト
    """
    servers = []

    # localhost
    servers.append({
        "url": f"http://localhost:{port}",
        "description": "ローカル開発環境"
    })

    # IPアドレス
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        servers.append({
            "url": f"http://{local_ip}:{port}",
            "description": f"IPアドレスアクセス ({local_ip})"
        })

    # ホスト名
    hostname = get_hostname()
    if hostname != "localhost":
        servers.append({
            "url": f"http://{hostname}:{port}",
            "description": f"ホスト名アクセス ({hostname})"
        })

    return servers


def test_hostname_resolution() -> dict:
    """
    ホスト名解決のテスト

    Returns:
        dict: テスト結果
    """
    import subprocess

    hostname = get_hostname()
    results = {
        "hostname": hostname,
        "ping_test": False,
        "dns_resolution": False,
        "resolved_ips": []
    }

    try:
        # Pingテスト
        ping_result = subprocess.run(
            ["ping", "-n", "1", hostname],
            capture_output=True,
            text=True,
            timeout=5
        )
        results["ping_test"] = ping_result.returncode == 0

        # DNS解決テスト
        import socket
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            results["dns_resolution"] = True
            results["resolved_ips"] = list(set([info[4][0] for info in addr_info]))
        except socket.gaierror:
            results["dns_resolution"] = False

    except Exception as e:
        logger.warning(f"ホスト名テストエラー: {e}")

    return results


def test_port_connectivity(host: str, port: int, timeout: int = 3) -> bool:
    """
    特定のホスト・ポートへの接続テスト

    Args:
        host: ホスト名またはIPアドレス
        port: ポート番号
        timeout: タイムアウト秒数

    Returns:
        bool: 接続可能かどうか
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception as e:
        logger.warning(f"接続テストエラー ({host}:{port}): {e}")
        return False


def diagnose_network_access(port: int = 8000) -> dict:
    """
    ネットワークアクセスの診断

    Args:
        port: サーバーポート番号

    Returns:
        dict: 診断結果
    """
    local_ip = get_local_ip()
    hostname = get_hostname()
    hostname_test = test_hostname_resolution()

    diagnosis = {
        "local_ip": local_ip,
        "hostname": hostname,
        "hostname_resolution": hostname_test,
        "connectivity": {
            "localhost": test_port_connectivity("127.0.0.1", port),
            "local_ip": test_port_connectivity(local_ip, port) if local_ip != "127.0.0.1" else False,
            "hostname": test_port_connectivity(hostname, port) if hostname != "localhost" else False
        }
    }

    return diagnosis


def print_access_info(port: int = 8000):
    """
    アクセス情報を表示

    Args:
        port: サーバーポート番号
    """
    print("\nアクセス方法:")

    # localhost
    print(f"  - http://localhost:{port} (ローカルアクセス)")

    # IPアドレス
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        print(f"  - http://{local_ip}:{port} (IPアドレス)")

    # ホスト名
    hostname = get_hostname()
    if hostname != "localhost":
        print(f"  - http://{hostname}:{port} (ホスト名)")

    print()


def print_network_diagnosis(port: int = 8000):
    """
    ネットワーク診断結果を表示

    Args:
        port: サーバーポート番号
    """
    diagnosis = diagnose_network_access(port)

    print(f"\n📊 ネットワーク診断結果 (ポート {port}):")
    print(f"  ローカルIP: {diagnosis['local_ip']}")
    print(f"  ホスト名: {diagnosis['hostname']}")

    # ホスト名解決
    hr = diagnosis["hostname_resolution"]
    print(f"  ホスト名解決: {'✅' if hr['dns_resolution'] else '❌'}")
    if hr["resolved_ips"]:
        print(f"    解決済みIP: {', '.join(hr['resolved_ips'])}")

    # 接続テスト
    conn = diagnosis["connectivity"]
    print(f"  接続テスト:")
    print(f"    localhost: {'✅' if conn['localhost'] else '❌'}")
    if diagnosis['local_ip'] != "127.0.0.1":
        print(f"    {diagnosis['local_ip']}: {'✅' if conn['local_ip'] else '❌'}")
    if diagnosis['hostname'] != "localhost":
        print(f"    {diagnosis['hostname']}: {'✅' if conn['hostname'] else '❌'}")

    print()