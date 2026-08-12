"""候補サイトを Firestore のサイト一覧へ追加する運用スクリプト。"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.config import CHECK_SOURCES_PATH, SOURCES_PATH, load_site_config  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402


def main() -> int:
    sources = load_site_config(SOURCES_PATH)
    candidates = load_site_config(CHECK_SOURCES_PATH)
    new_sources = {key: value for key, value in candidates.items() if key not in sources}
    for site_id in new_sources:
        print(f"New source: {site_id}")
    added = MinistrySiteDataGetter().add_site(new_sources)
    print(f"Added sites: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
