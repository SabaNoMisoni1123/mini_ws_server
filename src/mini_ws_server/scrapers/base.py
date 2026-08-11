"""スクレイパー共通の例外、定数、補助関数。"""

import hashlib


DEFAULT_TIMEOUT = 20


class ScrapeError(Exception):
    """単一サイトの取得または解析に失敗したことを表す例外。"""


def article_hash(url: str, title: str, epoch: int) -> str:
    """記事の重複判定に使う安定した SHA-256 ハッシュを返す。"""
    value = hashlib.sha256(str(url).encode("utf-8"))
    value.update(str(title).encode("utf-8"))
    value.update(str(epoch).encode("utf-8"))
    return value.hexdigest()
