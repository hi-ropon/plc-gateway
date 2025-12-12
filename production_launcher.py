"""PyInstaller用の本番専用ランチャー"""

from typing import List

from main import run

# exe からは常に本番モード/ホットリロード無効で起動する
DEFAULT_ARGS: List[str] = ["--production", "--no-reload", "--log-level", "INFO"]


def main():
    run(DEFAULT_ARGS)


if __name__ == "__main__":
    main()
