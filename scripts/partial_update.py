"""特定サイトを除外して更新結果をローカルに保存する手動スクリプト。"""

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.config import SOURCES_PATH, load_site_config  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402


def main() -> int:
    sources = load_site_config(SOURCES_PATH)
    sources.pop("metiShingikai", None)
    result = MinistrySiteDataGetter().update_all_data(sources)
    record = {"ws_result": result, "timestamp": datetime.now().strftime("%m/%d %H:%M:%S")}
    (PROJECT_ROOT / "sample.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
