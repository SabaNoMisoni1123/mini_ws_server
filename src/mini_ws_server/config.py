"""設定ファイルの場所と読込処理。"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
SOURCES_PATH = CONFIG_DIR / "sources.json"
DISABLED_SOURCES_PATH = CONFIG_DIR / "disabled_sources.json"
CHECK_SOURCES_PATH = PROJECT_ROOT / "checkUrlList.json"


def load_site_config(path: Path) -> dict:
    """サイト定義 JSON を読み込み、最上位がオブジェクトであることを検証する。"""
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON config: {path} line={exc.lineno} col={exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} must contain an object at the top level")
    return data
