import datetime as dt
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import firebase_admin
import requests
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore

import funclib


LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20


class ScrapeError(Exception):
    """Recoverable scraping error for one site."""


class MinistrySiteDataGetter:
    def __init__(self, credential_path="ws-db-11235813-firebase-adminsdk-lh4mi-50c38e64b5.json"):
        self.func_dict = {
            "micNews": funclib.get_mic_news,
            "digitalNews": funclib.get_digital_news,
            "mlitNews": funclib.get_mlit_news,
            "mlitIndividualNews": funclib.get_mlit_individual_news,
            "envCentralEarth": funclib.get_env_news_conf,
        }
        self._hash = funclib.art_hash
        self.errors = {}

        credential_path = Path(credential_path)
        if not credential_path.is_absolute():
            credential_path = Path(__file__).resolve().parent / credential_path

        if not firebase_admin._apps:
            cred = credentials.Certificate(str(credential_path))
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def update_all_data(self, site_dict: dict):
        results = {}
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
            self.db.collection("timeLog").document("lastTime").update(
                {"lastTimeEpoch": int(datetime.now().timestamp())}
            )
        except Exception:
            LOGGER.exception("Failed to update timeLog/lastTime")

        return results

    def _scraper(self, site_id, config: dict):
        self._validate_config(site_id, config)
        self.name = config["name"]
        self.url = config["url"]
        self.use_default_func = config["useDefaultFunc"]
        self.arg = config.get("arg", {})

        if self.use_default_func is True and self.arg.get("rss") is True:
            return self._get_w_feedparser()
        if self.use_default_func is True:
            return self._get_w_beautiful_soup()

        func_id = config.get("funcID")
        if func_id not in self.func_dict:
            raise ScrapeError(f"Unknown funcID: {func_id}")
        return self.func_dict[func_id](self.url, self.arg)

    def append_new_data(self, site_id, config: dict, days=3):
        data = self._scraper(site_id, config)
        if not data:
            LOGGER.warning("No scraped items: %s", site_id)
            return 0

        before_day = datetime.now() - timedelta(days=days)
        before_day = datetime(before_day.year, before_day.month, before_day.day)
        min_epoch = int(before_day.timestamp())
        data = [item for item in data if self._is_valid_item(item) and item["epoch"] >= min_epoch]

        current_hash = self._load_current_hashes(site_id)
        added = 0
        for item in data:
            if item["hash"] in current_hash:
                continue
            try:
                self._add_new_item(item, site_id)
                current_hash.add(item["hash"])
                added += 1
            except Exception:
                LOGGER.exception("Failed to add item: site=%s url=%s", site_id, item.get("url"))

        LOGGER.info("Added items: %s %s/%s", site_id, added, len(data))
        return added

    def _load_current_hashes(self, site_id):
        try:
            docs = (
                self.db.collection(site_id)
                .order_by("epoch", direction=firestore.Query.DESCENDING)
                .limit(50)
                .select(["hash"])
                .stream()
            )
            return {doc.to_dict().get("hash") for doc in docs if doc.to_dict().get("hash")}
        except Exception:
            LOGGER.exception("Failed to load current hashes: %s", site_id)
            return set()

    def _add_new_item(self, item: dict, site_id: str):
        self.db.collection(site_id).add(item)

    def _get_w_beautiful_soup(self):
        response = requests.get(self.url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        if "encoding" in self.arg:
            response.encoding = self.arg["encoding"]

        soup = BeautifulSoup(response.text, "html.parser")
        data = soup.select_one(self.arg["dataListPath"])
        if data is None:
            raise ScrapeError(f"Selector not found: {self.arg['dataListPath']}")
        return self._extract_data_from_soup(data)

    # Backward-compatible alias for existing scripts.
    def _get_w_beautifle_soup(self):
        return self._get_w_beautiful_soup()

    def _extract_data_from_soup(self, data):
        path = self.arg["path"]
        url_nodes = data.find_all(path["url"])
        title_nodes = data.find_all(path["title"])
        date_nodes = data.find_all(path["date"])
        org_nodes = data.find_all(path["org"]) if "org" in path else []

        ret_list = []
        for idx, (url_node, title_node, date_node) in enumerate(zip(url_nodes, title_nodes, date_nodes)):
            try:
                link = url_node.find("a")
                href = link.get("href") if link else None
                if not href:
                    continue
                title = title_node.get_text(strip=True)
                epoch = int(dt.datetime.strptime(date_node.get_text(strip=True), self.arg["dateFormat"]).timestamp())
                org = org_nodes[idx].get_text(strip=True) if idx < len(org_nodes) else self.name
                url = urljoin(self.arg.get("baseURL", self.url), href)
                ret_list.append({"url": url, "title": title, "epoch": epoch, "hash": self._hash(url, title, epoch), "org": org})
            except Exception:
                LOGGER.exception("Failed to parse default HTML item: %s", self.url)
        return ret_list

    def _get_w_feedparser(self):
        response = requests.get(self.url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        res = feedparser.parse(response.content)
        if getattr(res, "bozo", False):
            LOGGER.warning("Feed parse warning: %s %s", self.url, getattr(res, "bozo_exception", ""))

        data = self._move_feedparser_dict(res, self.arg["dataListPath"], default=[])
        ret_list = []
        for art in data:
            try:
                art_url = self._move_feedparser_dict(art, self.arg["path"]["url"])
                art_title = self._move_feedparser_dict(art, self.arg["path"]["title"])
                date_value = self._move_feedparser_dict(art, self.arg["path"]["date"])
                art_epoch = int(dt.datetime.strptime(str(date_value).replace("BST", "GMT"), self.arg["dateFormat"]).timestamp())
                org = (
                    self._move_feedparser_dict(art, self.arg["path"]["org"], default=self.name)
                    if "org" in self.arg["path"]
                    else self.name
                )
                ret_list.append({"url": art_url, "title": art_title, "epoch": art_epoch, "hash": self._hash(art_url, art_title, art_epoch), "org": org})
            except Exception:
                LOGGER.exception("Failed to parse feed item: %s", self.url)
        return ret_list

    # Backward-compatible alias for existing scripts.
    def _get_w_feedpaser(self):
        return self._get_w_feedparser()

    def _move_feedparser_dict(self, tree_dict, path, default=None):
        try:
            ret = tree_dict
            if isinstance(path, list):
                for p in path:
                    ret = ret[p]
                return ret
            return ret[path]
        except (KeyError, IndexError, TypeError):
            if default is not None:
                return default
            raise

    # Backward-compatible alias for existing scripts.
    def _move_feedpaser_dict(self, tree_dict, path):
        return self._move_feedparser_dict(tree_dict, path)

    def add_site(self, site_dict):
        docs = self.db.collection("siteData").select(["id"]).stream()
        current_site_ids = {doc.to_dict().get("id") for doc in docs if doc.to_dict().get("id")}
        no = len(current_site_ids)
        added = 0

        for site_id, config in site_dict.items():
            if site_id in current_site_ids:
                LOGGER.info("Already added: %s", site_id)
                continue
            new_item = {"id": site_id, "no": no, "name": config["name"], "url": config["url"]}
            self.db.collection("siteData").add(new_item)
            no += 1
            added += 1
        return added

    def test_new_source(self, site_id, config: dict):
        return self._scraper(site_id, config)

    def _validate_config(self, site_id, config):
        for key in ("name", "url", "useDefaultFunc", "arg"):
            if key not in config:
                raise ScrapeError(f"{site_id}: missing config key '{key}'")
        if config["useDefaultFunc"] is False and "funcID" not in config:
            raise ScrapeError(f"{site_id}: missing funcID")

    def _is_valid_item(self, item):
        required = ("url", "title", "epoch", "hash", "org")
        if not isinstance(item, dict) or any(key not in item for key in required):
            LOGGER.warning("Skip invalid item: %s", item)
            return False
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with open("./urlList.json", encoding="utf-8") as f:
        site_dict = json.load(f)

    ws_machine = MinistrySiteDataGetter()
    ret = ws_machine.update_all_data(site_dict)
    print(ret)
