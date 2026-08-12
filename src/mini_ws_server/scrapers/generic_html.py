"""設定駆動の HTML 一覧スクレイパー。"""

import datetime as dt
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import Article
from .base import DEFAULT_TIMEOUT, ScrapeError, article_hash


LOGGER = logging.getLogger(__name__)


def scrape(url: str, name: str, arg: dict) -> list[Article]:
    """設定された CSS/HTML パスから記事一覧を取得する。"""
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    if "encoding" in arg:
        response.encoding = arg["encoding"]

    soup = BeautifulSoup(response.text, "html.parser")
    data = soup.select_one(arg["dataListPath"])
    if data is None:
        raise ScrapeError(f"Selector not found: {arg['dataListPath']}")
    return _extract_items(data, url, name, arg)


def _extract_items(data, page_url: str, name: str, arg: dict) -> list[Article]:
    path = arg["path"]
    url_nodes = data.find_all(path["url"])
    title_nodes = data.find_all(path["title"])
    date_nodes = data.find_all(path["date"])
    org_nodes = data.find_all(path["org"]) if "org" in path else []
    items: list[Article] = []

    for index, (url_node, title_node, date_node) in enumerate(
        zip(url_nodes, title_nodes, date_nodes)
    ):
        try:
            link = url_node.find("a")
            href = link.get("href") if link else None
            if not href:
                continue
            title = title_node.get_text(strip=True)
            epoch = int(
                dt.datetime.strptime(
                    date_node.get_text(strip=True), arg["dateFormat"]
                ).timestamp()
            )
            org = org_nodes[index].get_text(strip=True) if index < len(org_nodes) else name
            item_url = urljoin(arg.get("baseURL", page_url), href)
            items.append(
                {
                    "url": item_url,
                    "title": title,
                    "epoch": epoch,
                    "hash": article_hash(item_url, title, epoch),
                    "org": org,
                }
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            LOGGER.exception("Failed to parse default HTML item: %s", page_url)
    return items
