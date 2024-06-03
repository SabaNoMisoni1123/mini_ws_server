import datetime as dt
import hashlib
import re

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta


# hash function
def art_hash(url, title, epoch):
    ret_hash = hashlib.sha256(url.encode())
    ret_hash.update(title.encode())
    ret_hash.update(str(epoch).encode())

    return ret_hash.hexdigest()


# ID: micNEWS
def get_mic_news(url, arg_dict):
    response = requests.get(url)
    response.encoding = "shift-jis"

    soup = BeautifulSoup(response.content, "html.parser")
    table_row = soup.find_all("tr")

    ret_list = []
    for r in table_row:
        cols = r.find_all("td")
        if len(cols) == 0 or "scope" not in cols[0].attrs:
            continue

        art_url = arg_dict["baseURL"] + cols[1].a.get("href")
        art_title = cols[1].string
        art_epoch = int(
            dt.datetime.strptime(cols[0].string, arg_dict["dateFormat"]).timestamp()
        )

        ret_list.append(
            {
                "epoch": art_epoch,
                "title": art_title,
                "url": art_url,
                "hash": art_hash(art_url, art_title, art_epoch),
                "org": cols[2].string,
            }
        )

    last_month = dt.datetime.today() + relativedelta(months=-1)
    url_last_month = (
        f"https://www.soumu.go.jp/menu_news/s-news/{last_month.strftime('%y%m')}m.html"
    )
    response = requests.get(url_last_month)
    response.encoding = "shift-jis"
    soup = BeautifulSoup(response.content, "html.parser")
    table_row = soup.find_all("tr")[1:]

    for r in table_row:
        cols = r.find_all("td")
        if len(cols) == 0 or "scope" not in cols[0].attrs:
            continue

        art_epoch = int(
            dt.datetime.strptime(cols[0].string, arg_dict["dateFormat"]).timestamp()
        )
        art_url = arg_dict["baseURL"] + cols[1].a.get("href")
        art_title = cols[1].string

        ret_list.append(
            {
                "epoch": art_epoch,
                "title": art_title,
                "url": art_url,
                "hash": art_hash(art_url, art_title, art_epoch),
                "org": cols[2].string,
            }
        )

    return ret_list


# ID: digitalNews
def get_digital_news(url, arg_dict):
    ret_list = []

    for i in range(arg_dict["nPage"]):
        url_sub = url + f"page={i}"
        response = requests.get(url_sub)
        soup = BeautifulSoup(response.content, "html.parser")
        for card in soup.select("section.card"):
            category = (
                card.select_one("span.card__category")
                .get_text()
                .replace(" ", "")
                .replace("\n", "")
            )
            if category in arg_dict["notWatchCategory"]:
                continue

            art_url = (
                arg_dict["baseURL"] + card.select_one("a").get("href")
                if card.select_one("a").get("href")[0] == "/"
                else card.select_one("a").get("href")
            )
            art_title = (
                f"（{category}） {card.select_one('.card__title > span').get_text()}"
            )
            art_epoch = int(
                dt.datetime.strptime(
                    card.select_one(".card__date > time").get("datetime"),
                    arg_dict["dateFormat"],
                ).timestamp()
            )

            ret_list.append(
                {
                    "url": art_url,
                    "title": art_title,
                    "epoch": art_epoch,
                    "hash": art_hash(art_url, art_title, art_epoch),
                    "org": "デジタル庁",
                }
            )

    return ret_list


# ID: mlitNews
def get_mlit_news(url, arg_dict):
    today = dt.datetime.now()
    last_month = dt.datetime.today() + relativedelta(months=-1)
    urls = [
        url + f"/houdou{today.strftime('%Y%m')}.html",
        url + f"/houdou{last_month.strftime('%Y%m')}.html",
    ]
    ret_list = []

    for u in urls:
        response = requests.get(u)
        soup = BeautifulSoup(response.content, "html.parser")

        data = soup.select_one(arg_dict["dataListPath"])

        art_epoch = 0
        for child in data.children:
            if child.name == "dt":
                art_epoch = int(
                    dt.datetime.strptime(
                        child.get_text(), arg_dict["dateFormat"]
                    ).timestamp()
                )
            elif child.name == "dd":
                art_title = child.a.get_text()
                art_url = arg_dict["baseURL"] + child.a.get("href")
                ret_list.append(
                    {
                        "epoch": art_epoch,
                        "title": art_title,
                        "url": art_url,
                        "hash": art_hash(art_url, art_title, art_epoch),
                        "org": "国交省新着情報",
                    }
                )
            else:
                continue

    return ret_list


# ID: mlitIndividualNews
def get_mlit_individual_news(url, arg_dict):
    ret_list = []
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    data = soup.select_one(arg_dict["dataListPath"])

    re_date = re.compile("（\d+年\d+月\d+日）")

    for article in data.find_all("a"):
        art_title = re_date.sub("", article.text)

        # 全角スペース対策
        art_title = re.sub(r"\\u([0-9a-fA-F]{4})", " ", art_title)
        art_title = art_title.replace("　", " ")

        art_epoch = int(
            dt.datetime.strptime(
                re_date.search(article.text).group(), arg_dict["dateFormat"]
            ).timestamp()
        )
        art_url = arg_dict["baseURL"] + article.get("href")

        ret_list.append(
            {
                "epoch": art_epoch,
                "title": art_title,
                "url": art_url,
                "hash": art_hash(art_url, art_title, art_epoch),
                "org": "国土交通省",
            }
        )

    return ret_list
