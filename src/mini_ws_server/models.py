"""アプリケーション内で扱うデータの型定義。"""

from typing import NotRequired, TypedDict


class Article(TypedDict):
    url: str
    title: str
    epoch: int
    hash: str
    org: str


class SiteConfig(TypedDict):
    name: str
    url: str
    useDefaultFunc: bool
    arg: dict
    funcID: NotRequired[str]
