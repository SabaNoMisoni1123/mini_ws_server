"""記事取得から重複判定・保存までを調整するアプリケーションサービス。"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .models import Article
from .scrapers.base import ScrapeError, article_hash


if TYPE_CHECKING:
    from .repositories.firestore import FirestoreRepository


LOGGER = logging.getLogger(__name__)


class MinistrySiteDataGetter:
    """既存のサイト定義を読み、Firestore へ新着記事を追加する。"""

    def __init__(self, credential_path=None, repository=None):
        self.func_dict = {
            "micNews": "get_mic_news",
            "digitalNews": "get_digital_news",
            "mlitNews": "get_mlit_news",
            "mlitIndividualNews": "get_mlit_individual_news",
            "envCentralEarth": "get_env_news_conf",
        }
        self._hash = article_hash
        self.errors: dict[str, str] = {}
        if repository is None:
            from .repositories.firestore import FirestoreRepository

            repository = FirestoreRepository(credential_path)
        self.repository = repository

    def update_all_data(self, site_dict: dict) -> dict[str, int]:
        results: dict[str, int] = {}
        self.errors = {}
        for site_id, config in site_dict.items():
            LOGGER.info("Start site: %s", site_id)
            try:
                results[site_id] = self.append_new_data(site_id, config)
            except Exception as exc:
                LOGGER.exception("Failed site: %s", site_id)
                self.errors[site_id] = str(exc)
                results[site_id] = -1

        try:
            self.repository.update_last_run(int(datetime.now().timestamp()))
        except Exception:
            LOGGER.exception("Failed to update timeLog/lastTime")
        return results

    def append_new_data(self, site_id: str, config: dict, days: int = 3) -> int:
        data = self._scraper(site_id, config)
        if not data:
            LOGGER.warning("No scraped items: %s", site_id)
            return 0

        before_day = datetime.now() - timedelta(days=days)
        minimum_epoch = int(datetime(before_day.year, before_day.month, before_day.day).timestamp())
        valid_items = [
            item for item in data if self._is_valid_item(item) and item["epoch"] >= minimum_epoch
        ]
        current_hashes = self.repository.load_current_hashes(site_id)
        added = 0
        for item in valid_items:
            if item["hash"] in current_hashes:
                continue
            try:
                self.repository.add_article(site_id, item)
                current_hashes.add(item["hash"])
                added += 1
            except Exception:
                LOGGER.exception("Failed to add item: site=%s url=%s", site_id, item.get("url"))
        LOGGER.info("Added items: %s %s/%s", site_id, added, len(valid_items))
        return added

    def _scraper(self, site_id: str, config: dict) -> list[Article]:
        from .scrapers import generic_feed, generic_html, ministries

        self._validate_config(site_id, config)
        name = config["name"]
        url = config["url"]
        arg = config.get("arg", {})
        if config["useDefaultFunc"]:
            return generic_feed.scrape(url, name, arg) if arg.get("rss") else generic_html.scrape(url, name, arg)

        func_id = config.get("funcID")
        if func_id not in self.func_dict:
            raise ScrapeError(f"Unknown funcID: {func_id}")
        return getattr(ministries, self.func_dict[func_id])(url, arg)

    def add_site(self, site_dict: dict) -> int:
        return self.repository.add_sites(site_dict)

    def test_new_source(self, site_id: str, config: dict) -> list[Article]:
        return self._scraper(site_id, config)

    @staticmethod
    def _validate_config(site_id: str, config: dict) -> None:
        for key in ("name", "url", "useDefaultFunc", "arg"):
            if key not in config:
                raise ScrapeError(f"{site_id}: missing config key '{key}'")
        if config["useDefaultFunc"] is False and "funcID" not in config:
            raise ScrapeError(f"{site_id}: missing funcID")

    @staticmethod
    def _is_valid_item(item: object) -> bool:
        required = ("url", "title", "epoch", "hash", "org")
        if not isinstance(item, dict) or any(key not in item for key in required):
            LOGGER.warning("Skip invalid item: %s", item)
            return False
        return True
