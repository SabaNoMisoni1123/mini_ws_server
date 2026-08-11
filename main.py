"""後方互換のための CLI 入口。実装は ``src/mini_ws_server/cli.py`` にある。"""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mini_ws_server.cli import command_line_main, main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(command_line_main(sys.argv[1:]))
