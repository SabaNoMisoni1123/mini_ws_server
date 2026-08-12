"""候補サイトを1件だけ取得して結果を確認する運用スクリプト。"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.config import CHECK_SOURCES_PATH, load_site_config  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402


HELP_TEXT = "このヘルプを表示して終了します。"


def main() -> int:
    """候補情報元を取得して、保存せずに解析結果を表示する。"""
    parser = argparse.ArgumentParser(
        description="候補情報元を1件取得し、Firestore へ保存せずに解析結果を表示します。",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help=HELP_TEXT)
    parser.add_argument(
        "site_id",
        nargs="?",
        metavar="SITE_ID",
        help="確認する候補情報元のID。省略時は設定ファイルの先頭の候補を使用します。",
    )
    args = parser.parse_args()
    sources = load_site_config(CHECK_SOURCES_PATH)
    site_id = args.site_id or next(iter(sources), None)
    if site_id is None or site_id not in sources:
        raise RuntimeError(f"Unknown site_id: {site_id}")
    print(site_id)
    print(MinistrySiteDataGetter().test_new_source(site_id, sources[site_id]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
