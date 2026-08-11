"""互換モジュール。サイト固有パーサーは ``scrapers/ministries.py`` にある。"""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mini_ws_server.scrapers.ministries import (  # noqa: E402,F401
    art_hash,
    get_digital_news,
    get_env_news_conf,
    get_mic_news,
    get_mlit_individual_news,
    get_mlit_news,
    wareki_year,
)

__all__ = [
    "art_hash",
    "get_digital_news",
    "get_env_news_conf",
    "get_mic_news",
    "get_mlit_individual_news",
    "get_mlit_news",
    "wareki_year",
]
