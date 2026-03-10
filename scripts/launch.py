"""Streamlit アプリランチャー — 空きポートを自動選択して起動"""

import socket
import subprocess
import sys

DEFAULT_PORT = 8501
PORT_RANGE = range(8501, 8600)


def is_port_in_use(port: int) -> bool:
    """指定ポートが使用中かチェック"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("localhost", port)) == 0


def find_available_port() -> int:
    """空きポートを探して返す"""
    for port in PORT_RANGE:
        if not is_port_in_use(port):
            return port
    raise RuntimeError(f"ポート {PORT_RANGE.start}-{PORT_RANGE.stop - 1} はすべて使用中です")


def main():
    port = find_available_port()

    if port != DEFAULT_PORT:
        print(f"ポート {DEFAULT_PORT} は使用中です。ポート {port} で起動します。")
    else:
        print(f"ポート {port} で起動します。")

    print(f"URL: http://localhost:{port}")
    print()

    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run", "app/main.py",
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
    )


if __name__ == "__main__":
    main()
