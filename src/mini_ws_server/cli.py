"""本番更新処理のコマンドライン入口。"""

import json
import logging
from pathlib import Path

from .config import SOURCES_PATH, load_site_config
from .service import MinistrySiteDataGetter


def main() -> int:
    """サイト定義を読み込み、全サイトの新着情報を更新する。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path.cwd() / "scraper.log", encoding="utf-8"),
        ],
    )
    try:
        site_dict = load_site_config(SOURCES_PATH)
        scraper = MinistrySiteDataGetter()
        result = scraper.update_all_data(site_dict)
    except Exception:
        logging.exception("Fatal error")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if scraper.errors:
        logging.error("Completed with site errors: %s", scraper.errors)
    return 0
