import datetime as dt
import json
import os
from datetime import datetime, timedelta

import feedparser
import firebase_admin
import requests
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore

import funclib


class MinistrySiteDataGetter:
    def __init__(self):
        # 個別に実装した関数の登録
        self.func_dict = {
            "micNews": funclib.get_mic_news,
            "digitalNews": funclib.get_digital_news,
            "mlitNews": funclib.get_mlit_news,
            "mlitIndividualNews": funclib.get_mlit_individual_news,
        }
        print("FIREBASE_CRED_FNAME", os.getenv("FIREBASE_CRED_FNAME"))

        cred = credentials.Certificate(os.getenv("FIREBASE_CRED_FNAME"))
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()

        self._hash = funclib.art_hash

    def update_all_data(self, site_dict: dict):
        new_items = {}
        for k in site_dict.keys():
            print(k)
            config = site_dict[k]
            new_items[k] = self.append_new_data(k, config)

        self.db.collection("timeLog").document("lastTime").update(
            {"lastTimeEpoch": int(datetime.now().timestamp() // 1000)}
        )
        return new_items

    def append_new_data(self, id, config: dict):
        self.name = config["name"]
        self.url = config["url"]
        self.use_default_func = config["useDefaultFunc"]
        self.arg = config["arg"]

        if self.use_default_func is True and self.arg["rss"] is True:
            # RSSの読み取り
            data = self._get_w_feedpaser()
        elif self.use_default_func is True:
            # ウェブスクレイプをデフォルト関数で実施
            data = self._get_w_beautifle_soup()
        else:
            # ウェブスクレイプを個別関数で実施
            data = self.func_dict[config["funcID"]](self.url, self.arg)

        # dataを過去3日分とする
        today = datetime.now()
        before_day = today - timedelta(days=3)
        before_day = datetime(
            year=before_day.year, month=before_day.month, day=before_day.day
        )
        data = [item for item in data if item["epoch"] >= int(before_day.timestamp())]

        # 既存の記事
        current_hash = [
            doc.get("hash")
            for doc in self.db.collection(id)
            .order_by("epoch", direction=firestore.Query.DESCENDING)
            .limit(50)
            .select(["hash"])
            .stream()
        ]

        n_new_item = 0
        for item in data:
            # ハッシュから、既存の記事なのか確認
            if item["hash"] in current_hash:
                continue
            else:
                # 追加
                self._add_new_item(item, id)
                n_new_item += 1

        print(f"\tNumber of added Items: {n_new_item}")
        return n_new_item

    def _add_new_item(self, item: dict, siteId: str):
        self.db.collection(siteId).add(item)

    def _get_w_beautifle_soup(self):
        response = requests.get(self.url)

        if "encording" in self.arg.keys():
            response.encoding = self.arg["encoding"]

        soup = BeautifulSoup(response.content, "html.parser")
        data = soup.select(self.arg["dataListPath"])[0]

        return self._extract_data_from_soup(data)

    def _extract_data_from_soup(self, data):
        url_list = [
            self.arg["baseURL"] + u.find("a").get("href")
            for u in data.find_all(self.arg["path"]["url"])
        ]
        title_list = [t.get_text() for t in data.find_all(self.arg["path"]["title"])]
        date_list = [
            int(dt.datetime.strptime(d.get_text(), self.arg["dateFormat"]).timestamp())
            for d in data.find_all(self.arg["path"]["date"])
        ]

        if "org" in self.arg["path"].keys():
            org_list = [t.get_text() for t in data.find_all(self.arg["path"]["org"])]
        else:
            org_list = [self.name] * len(url_list)

        ret_list = []
        for u, t, d, o in zip(url_list, title_list, date_list, org_list):
            ret_list.append(
                {
                    "url": u,
                    "title": t,
                    "epoch": d,
                    "hash": self._hash(u, t, d),
                    "org": o,
                }
            )

        return ret_list

    def _get_w_feedpaser(self):
        ret_list = []
        res = feedparser.parse(self.url)
        data = self._move_feedpaser_dict(res, self.arg["dataListPath"])

        for art in data:
            art_url = self._move_feedpaser_dict(art, self.arg["path"]["url"])
            art_title = self._move_feedpaser_dict(art, self.arg["path"]["title"])
            art_epoch = int(
                dt.datetime.strptime(
                    art[self.arg["path"]["date"]].replace("BST", "GMT"),
                    self.arg["dateFormat"],
                ).timestamp()
            )

            art_dict = {
                "url": art_url,
                "title": art_title,
                "epoch": art_epoch,
                "hash": self._hash(art_url, art_title, art_epoch),
            }
            if "org" in self.arg["path"].keys():
                art_dict["org"] = self._move_feedpaser_dict(
                    art, self.arg["path"]["org"]
                )
            else:
                art_dict["org"] = self.name
            ret_list.append(art_dict)

        return ret_list

    def _move_feedpaser_dict(self, tree_dict, path):
        ret = tree_dict
        if type(path) is list:
            for p in path:
                ret = ret[p]
        else:
            ret = ret[path]

        return ret

    def add_site(self, site_dict):
        docs = self.db.collection("siteData").select(["id"]).stream()
        current_site_ids = [
            doc.to_dict().get("id") for doc in docs if doc.to_dict().get("id")
        ]

        print(current_site_ids)
        no = len(current_site_ids)
        ret_no = 0

        for k in site_dict.keys():
            if k in current_site_ids:
                continue
            else:
                new_item = {
                    "id": k,
                    "no": no,
                    "name": site_dict[k]["name"],
                    "url": site_dict[k]["url"],
                }

                self.db.collection("siteData").add(new_item)
                no += 1
                ret_no += 1
        return ret_no


if __name__ == "__main__":
    site_dict = dict()
    with open("./urlList.json", encoding="utf-8") as f:
        site_dict = json.load(f)

    ws_machine = MinistrySiteDataGetter()
    ret = ws_machine.update_all_data(site_dict)
    print(ret)
