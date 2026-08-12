import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.data_transfer import ArticleDataTransfer, read_articles, write_articles  # noqa: E402


ARTICLE = {"url": "https://example.test/1", "title": "記事", "epoch": 100, "hash": "hash-1", "org": "省庁"}


class FakeRepository:
    def __init__(self):
        self.articles = [ARTICLE.copy()]
        self.hashes = {"hash-1"}
        self.added = []
        self.deleted_site_id = None

    def list_articles(self, site_id):
        return self.articles

    def load_all_hashes(self, site_id):
        return self.hashes.copy()

    def add_article(self, site_id, article):
        self.added.append((site_id, article))

    def delete_site_articles(self, site_id):
        self.deleted_site_id = site_id
        return len(self.articles)


class ArticleDataTransferTest(unittest.TestCase):
    def test_json_export_and_import_only_adds_unknown_hashes(self):
        repository = FakeRepository()
        transfer = ArticleDataTransfer(repository)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.json"
            self.assertEqual(transfer.export_articles("example", path), 1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [ARTICLE])
            path.write_text(json.dumps([ARTICLE, {**ARTICLE, "hash": "hash-2"}]), encoding="utf-8")
            added, skipped = transfer.import_articles("example", path)
        self.assertEqual((added, skipped), (1, 1))
        self.assertEqual(repository.added[0], ("example", {**ARTICLE, "hash": "hash-2"}))

    def test_csv_round_trip_converts_epoch_to_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.csv"
            write_articles(path, [ARTICLE])
            self.assertEqual(read_articles(path), [ARTICLE])

    def test_export_preserves_hash_in_json_and_csv(self):
        repository = FakeRepository()
        transfer = ArticleDataTransfer(repository)
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "articles.json"
            csv_path = Path(directory) / "articles.csv"

            transfer.export_articles("example", json_path)
            transfer.export_articles("example", csv_path)

            self.assertEqual(
                json.loads(json_path.read_text(encoding="utf-8"))[0]["hash"], "hash-1"
            )
            with csv_path.open(encoding="utf-8", newline="") as file:
                self.assertEqual(next(csv.DictReader(file))["hash"], "hash-1")

    def test_export_overwrites_an_existing_file(self):
        repository = FakeRepository()
        transfer = ArticleDataTransfer(repository)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.json"
            path.write_text('[{"old": true}]', encoding="utf-8")

            transfer.export_articles("example", path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [ARTICLE])

    def test_export_then_delete_happens_after_file_is_written(self):
        repository = FakeRepository()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.json"
            self.assertEqual(ArticleDataTransfer(repository).export_and_delete_articles("example", path), 1)
            self.assertTrue(path.exists())
        self.assertEqual(repository.deleted_site_id, "example")

    def test_csv_without_headers_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                csv.writer(file).writerow(["wrong"])
            with self.assertRaisesRegex(ValueError, "missing required headers"):
                read_articles(path)


if __name__ == "__main__":
    unittest.main()
