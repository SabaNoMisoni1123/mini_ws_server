import json
import logging
import sys
from pathlib import Path

from wslib import MinistrySiteDataGetter


ROOT_DIR = Path(__file__).resolve().parent
URL_LIST_PATH = ROOT_DIR / "urlList.json"


def load_site_config(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON config: {path} line={exc.lineno} col={exc.colno}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("urlList.json must contain an object at the top level")
    return data


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT_DIR / "scraper.log", encoding="utf-8"),
        ],
    )

    try:
        site_dict = load_site_config(URL_LIST_PATH)
        ws_machine = MinistrySiteDataGetter()
        result = ws_machine.update_all_data(site_dict)
    except Exception:
        logging.exception("Fatal error")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if ws_machine.errors:
        logging.error("Completed with site errors: %s", ws_machine.errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
