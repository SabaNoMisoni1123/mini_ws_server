"""設定駆動の RSS/Atom スクレイパー。"""

import datetime as dt
import logging

import feedparser
import requests

from ..models import Article
from .base import DEFAULT_TIMEOUT, article_hash


LOGGER = logging.getLogger(__name__)


def scrape(url: str, name: str, arg: dict) -> list[Article]:
    """設定されたフィードのパスから記事一覧を取得する。"""
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False):
        LOGGER.warning("Feed parse warning: %s %s", url, getattr(feed, "bozo_exception", ""))

    items: list[Article] = []
    for article in _get_path(feed, arg["dataListPath"], default=[]):
        try:
            article_url = _get_path(article, arg["path"]["url"])
            title = _get_path(article, arg["path"]["title"])
            date_value = _get_path(article, arg["path"]["date"])
            epoch = int(
                dt.datetime.strptime(
                    str(date_value).replace("BST", "GMT"), arg["dateFormat"]
                ).timestamp()
            )
            org = (
                _get_path(article, arg["path"]["org"], default=name)
                if "org" in arg["path"]
                else name
            )
            items.append(
                {
                    "url": article_url,
                    "title": title,
                    "epoch": epoch,
                    "hash": article_hash(article_url, title, epoch),
                    "org": org,
                }
            )
        except (KeyError, IndexError, TypeError, ValueError):
            LOGGER.exception("Failed to parse feed item: %s", url)
    return items


def _get_path(tree: object, path: str | list[str], default=None):
    try:
        value = tree
        for part in path if isinstance(path, list) else [path]:
            value = value[part]
        return value
    except (KeyError, IndexError, TypeError):
        if default is not None:
            return default
        raise
