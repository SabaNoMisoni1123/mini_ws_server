"""互換モジュール。実装は :mod:`mini_ws_server.service` に移動済み。"""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mini_ws_server.scrapers.base import ScrapeError  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402

__all__ = ["MinistrySiteDataGetter", "ScrapeError"]
