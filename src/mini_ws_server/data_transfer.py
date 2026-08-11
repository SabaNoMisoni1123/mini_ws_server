"""Firestore の記事データをファイルへ入出力する運用ユースケース。"""

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .repositories.firestore import FirestoreRepository


ARTICLE_FIELDS = ("url", "title", "epoch", "hash", "org")


class ArticleDataTransfer:
    """情報元ごとの記事をエクスポート、重複なしでインポート、削除する。"""

    def __init__(self, repository: "FirestoreRepository"):
        self.repository = repository

    def export_articles(self, site_id: str, output_path: str | Path) -> int:
        """指定情報元の記事を JSON または CSV として保存する。"""
        articles = self.repository.list_articles(site_id)
        write_articles(output_path, articles)
        return len(articles)

    def import_articles(self, site_id: str, input_path: str | Path) -> tuple[int, int]:
        """ファイル内で有効かつ未登録の記事だけを Firestore へ追加する。"""
        articles = read_articles(input_path)
        existing_hashes = self.repository.load_all_hashes(site_id)
        added = 0
        skipped = 0
        for article in articles:
            if article["hash"] in existing_hashes:
                skipped += 1
                continue
            self.repository.add_article(site_id, article)
            existing_hashes.add(article["hash"])
            added += 1
        return added, skipped

    def export_and_delete_articles(self, site_id: str, output_path: str | Path) -> int:
        """記事をファイルへ正常に保存した後で、指定情報元の記事だけを削除する。"""
        self.export_articles(site_id, output_path)
        return self.repository.delete_site_articles(site_id)


def read_articles(input_path: str | Path) -> list[dict]:
    """JSON または CSV の記事ファイルを読み、データ契約を検証する。"""
    path = Path(input_path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {path}") from exc
        if not isinstance(value, list):
            raise ValueError("JSON must contain an array of articles.")
        rows = value
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        if not rows and not _has_article_headers(path):
            raise ValueError(f"CSV is missing required headers: {', '.join(ARTICLE_FIELDS)}")
    else:
        raise ValueError("Input file must have a .json or .csv extension.")

    return [_validate_article(row, index + 1) for index, row in enumerate(rows)]


def write_articles(output_path: str | Path, articles: list[dict]) -> None:
    """記事を JSON または CSV として保存する。既存ファイルは上書きしない。"""
    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"Output file already exists: {path}")
    suffix = path.suffix.lower()
    rows = [_validate_article(article, index + 1) for index, article in enumerate(articles)]
    if suffix == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif suffix == ".csv":
        with path.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=ARTICLE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    else:
        raise ValueError("Output file must have a .json or .csv extension.")


def _has_article_headers(path: Path) -> bool:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        headers = csv.reader(file)
        first_row = next(headers, [])
    return set(ARTICLE_FIELDS).issubset(first_row)


def _validate_article(value: object, row_number: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Row {row_number}: article must be an object.")
    missing = [field for field in ARTICLE_FIELDS if value.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Row {row_number}: missing required fields: {', '.join(missing)}")
    try:
        epoch = int(value["epoch"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {row_number}: epoch must be an integer.") from exc
    if any(not isinstance(value[field], str) for field in ("url", "title", "hash", "org")):
        raise ValueError(f"Row {row_number}: url, title, hash, and org must be strings.")
    return {"url": value["url"], "title": value["title"], "epoch": epoch,
            "hash": value["hash"], "org": value["org"]}
