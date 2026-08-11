"""候補サイトを1件だけ取得して結果を確認する運用スクリプト。"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.config import CHECK_SOURCES_PATH, load_site_config  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_id", nargs="?", help="確認するサイトID（未指定時は先頭）")
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
