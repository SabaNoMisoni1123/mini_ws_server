"""本番更新処理のコマンドライン入口。"""

import argparse
import json
import logging
from pathlib import Path

from .config import SOURCES_PATH, load_site_config
from .service import MinistrySiteDataGetter


def _positive_int(value: str) -> int:
    """正の整数を引数として受け付ける。"""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("正の整数を指定してください") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください")
    return parsed


def main(days_range: int = 3) -> int:
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
        result = scraper.update_all_data(site_dict, days=days_range)
    except Exception:
        logging.exception("Fatal error")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if scraper.errors:
        logging.error("Completed with site errors: %s", scraper.errors)
    return 0


def command_line_main(argv: list[str] | None = None) -> int:
    """コマンドライン引数を解釈して本番更新を実行する。"""
    parser = argparse.ArgumentParser(
        description="全情報元の新着情報を取得し、Firestore を更新します。"
    )
    parser.add_argument(
        "--days-range",
        type=_positive_int,
        default=3,
        metavar="N",
        help="確認する過去の日数（実行日を基準、既定値: 3）。",
    )
    args = parser.parse_args(argv)
    return main(days_range=args.days_range)
