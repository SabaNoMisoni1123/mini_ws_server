import datetime as dt
import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from .base import DEFAULT_TIMEOUT, article_hash


LOGGER = logging.getLogger(__name__)
art_hash = article_hash


def wareki_year(y_wareki: str):
    if not y_wareki:
        raise ValueError("empty wareki year")
    nengo = y_wareki[0].upper()
    y = int(y_wareki[1:], 10)

    if nengo == "R":
        return y + 2018
    if nengo == "H":
        return y + 1988
    return y


def _get_soup(url, encoding=None):
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    if encoding:
        response.encoding = encoding
    return BeautifulSoup(response.text, "html.parser")


def _parse_epoch(value, date_format):
    return int(dt.datetime.strptime(value.strip(), date_format).timestamp())


def _text(node, default=""):
    return node.get_text(strip=True) if node is not None else default


def get_mic_news(url, arg_dict):
    ret_list = []
    targets = [url]
    last_month = dt.datetime.today() + relativedelta(months=-1)
    targets.append(f"https://www.soumu.go.jp/menu_news/s-news/{last_month.strftime('%y%m')}m.html")

    for target_url in targets:
        soup = _get_soup(target_url, encoding="shift-jis")
        for row in soup.find_all("tr"):
            try:
                cols = row.find_all("td")
                if len(cols) < 3 or "scope" not in cols[0].attrs or cols[1].a is None:
                    continue
                art_epoch = _parse_epoch(_text(cols[0]), arg_dict["dateFormat"])
                art_url = urljoin(arg_dict["baseURL"], cols[1].a.get("href"))
                art_title = _text(cols[1])
                ret_list.append(
                    {
                        "epoch": art_epoch,
                        "title": art_title,
                        "url": art_url,
                        "hash": art_hash(art_url, art_title, art_epoch),
                        "org": _text(cols[2], "総務省"),
                    }
                )
            except Exception:
                LOGGER.exception("Failed to parse MIC news row: %s", target_url)
    return ret_list


def get_digital_news(url, arg_dict):
    ret_list = []
    for i in range(arg_dict.get("nPage", 1)):
        url_sub = url + f"page={i}"
        soup = _get_soup(url_sub)
        for card in soup.select(arg_dict.get("dataListPath", "section.card")):
            try:
                category = _text(card.select_one("span.card__category")).replace(" ", "").replace("\n", "")
                if category in arg_dict.get("notWatchCategory", []):
                    continue

                link = card.select_one("a")
                href = link.get("href") if link else None
                title_node = card.select_one(".card__title > span")
                time_node = card.select_one(".card__date > time")
                if not href or title_node is None or time_node is None:
                    continue

                art_url = urljoin(arg_dict["baseURL"], href)
                art_title = f"【{category}】{_text(title_node)}" if category else _text(title_node)
                art_epoch = _parse_epoch(time_node.get("datetime", ""), arg_dict["dateFormat"])
                ret_list.append(
                    {
                        "url": art_url,
                        "title": art_title,
                        "epoch": art_epoch,
                        "hash": art_hash(art_url, art_title, art_epoch),
                        "org": "デジタル庁",
                    }
                )
            except Exception:
                LOGGER.exception("Failed to parse Digital Agency card: %s", url_sub)
    return ret_list


def get_mlit_news(url, arg_dict):
    today = dt.datetime.now()
    last_month = dt.datetime.today() + relativedelta(months=-1)
    urls = [
        url + f"/houdou{today.strftime('%Y%m')}.html",
        url + f"/houdou{last_month.strftime('%Y%m')}.html",
    ]
    ret_list = []

    for target_url in urls:
        soup = _get_soup(target_url)
        data = soup.select_one(arg_dict["dataListPath"])
        if data is None:
            LOGGER.warning("MLIT data selector not found: %s", target_url)
            continue

        art_epoch = None
        for child in data.children:
            try:
                if child.name == "dt":
                    art_epoch = _parse_epoch(_text(child), arg_dict["dateFormat"])
                elif child.name == "dd" and child.a is not None and art_epoch is not None:
                    art_title = _text(child.a)
                    art_url = urljoin(arg_dict["baseURL"], child.a.get("href"))
                    ret_list.append(
                        {
                            "epoch": art_epoch,
                            "title": art_title,
                            "url": art_url,
                            "hash": art_hash(art_url, art_title, art_epoch),
                            "org": "国土交通省",
                        }
                    )
            except Exception:
                LOGGER.exception("Failed to parse MLIT news item: %s", target_url)
    return ret_list


def get_mlit_individual_news(url, arg_dict):
    ret_list = []
    soup = _get_soup(url)
    data = soup.select_one(arg_dict["dataListPath"])
    if data is None:
        LOGGER.warning("MLIT individual selector not found: %s", url)
        return ret_list

    re_date = re.compile(r"（\d{4}年\d{1,2}月\d{1,2}日）")
    for article in data.find_all("a"):
        try:
            match = re_date.search(article.get_text())
            if match is None:
                continue
            art_title = re_date.sub("", article.get_text(" ", strip=True)).replace("\u3000", " ").strip()
            art_epoch = _parse_epoch(match.group(), arg_dict["dateFormat"])
            art_url = urljoin(arg_dict["baseURL"], article.get("href"))
            ret_list.append(
                {
                    "epoch": art_epoch,
                    "title": art_title,
                    "url": art_url,
                    "hash": art_hash(art_url, art_title, art_epoch),
                    "org": "国土交通省",
                }
            )
        except Exception:
            LOGGER.exception("Failed to parse MLIT individual item: %s", url)
    return ret_list


def get_env_news_conf(url, arg_dict):
    ret_list = []
    soup = _get_soup(url)
    data = soup.select_one(arg_dict["dataListPath"])
    if data is None:
        LOGGER.warning("Environment selector not found: %s", url)
        return ret_list

    re_date = re.compile(r"[A-Z]\d{1,2}\.\d{1,2}\.\d{1,2}")
    for article in data.find_all("li"):
        try:
            art_title = article.get_text(" ", strip=True)
            match = re_date.search(art_title)
            link = article.select_one("a")
            if match is None or link is None:
                continue
            art_date_str = match.group().split(".")
            art_epoch = int(
                dt.datetime(
                    year=wareki_year(art_date_str[0]),
                    month=int(art_date_str[1], 10),
                    day=int(art_date_str[2], 10),
                ).timestamp()
            )
            art_url = urljoin(arg_dict["baseURL"], link.get("href"))
            ret_list.append(
                {
                    "epoch": art_epoch,
                    "title": art_title,
                    "url": art_url,
                    "hash": art_hash(art_url, art_title, art_epoch),
                    "org": "環境省",
                }
            )
        except Exception:
            LOGGER.exception("Failed to parse Environment Council item: %s", url)
    return ret_list
