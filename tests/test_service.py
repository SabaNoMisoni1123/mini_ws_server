import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402


class FakeRepository:
    def __init__(self):
        self.items = []

    def load_current_hashes(self, site_id):
        return {"already-exists"}

    def add_article(self, site_id, item):
        self.items.append((site_id, item))

    def update_last_run(self, epoch):
        self.last_run = epoch


class ServiceTest(unittest.TestCase):
    def test_append_skips_known_hash_and_saves_new_item(self):
        repository = FakeRepository()
        service = MinistrySiteDataGetter(repository=repository)
        service._scraper = lambda *_: [
            {"url": "https://example.test/old", "title": "old", "epoch": 9_999_999_999, "hash": "already-exists", "org": "Example"},
            {"url": "https://example.test/new", "title": "new", "epoch": 9_999_999_999, "hash": "new", "org": "Example"},
        ]

        added = service.append_new_data("example", {"unused": True})

        self.assertEqual(added, 1)
        self.assertEqual(repository.items[0][1]["hash"], "new")

    def test_source_failure_does_not_stop_remaining_sources(self):
        repository = Mock()
        service = MinistrySiteDataGetter(repository=repository)
        service.append_new_data = Mock(side_effect=[RuntimeError("failed"), 2])
        sources = {"failed": {}, "succeeded": {}}

        result = service.update_all_data(sources)

        self.assertEqual(result.added, {"failed": 0, "succeeded": 2})
        self.assertEqual(result.errors[0].scope, "source")
        self.assertEqual(result.errors[0].source_id, "failed")
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(dict(result), {"failed": 0, "succeeded": 2})
        self.assertEqual(result, {"failed": 0, "succeeded": 2})
        self.assertIsInstance(result, dict)
        self.assertEqual(
            service.append_new_data.call_args_list,
            [
                call("failed", sources["failed"], days=3),
                call("succeeded", sources["succeeded"], days=3),
            ],
        )

    def test_article_failure_is_aggregated_and_other_articles_continue(self):
        repository = Mock()
        repository.load_current_hashes.return_value = set()
        repository.add_article.side_effect = [RuntimeError("write failed"), None]
        service = MinistrySiteDataGetter(repository=repository)
        service._scraper = Mock(
            return_value=[
                {
                    "url": "https://example.test/first",
                    "title": "first",
                    "epoch": 9_999_999_999,
                    "hash": "first",
                    "org": "Example",
                },
                {
                    "url": "https://example.test/second",
                    "title": "second",
                    "epoch": 9_999_999_999,
                    "hash": "second",
                    "org": "Example",
                },
            ]
        )

        result = service.update_all_data({"example": {}})

        self.assertEqual(result.added, {"example": 1})
        self.assertEqual([error.scope for error in result.errors], ["article"])
        self.assertEqual(repository.add_article.call_count, 2)

    def test_last_run_failure_is_aggregated(self):
        repository = Mock()
        repository.update_last_run.side_effect = RuntimeError("timestamp failed")
        service = MinistrySiteDataGetter(repository=repository)

        result = service.update_all_data({})

        self.assertFalse(result.success)
        self.assertEqual(result.errors[0].scope, "last_run")

    def test_hash_load_failure_skips_all_article_writes_for_source(self):
        repository = Mock()
        repository.load_current_hashes.side_effect = RuntimeError("read failed")
        service = MinistrySiteDataGetter(repository=repository)
        service._scraper = Mock(
            return_value=[
                {
                    "url": "https://example.test/article",
                    "title": "article",
                    "epoch": 9_999_999_999,
                    "hash": "article",
                    "org": "Example",
                }
            ]
        )

        result = service.update_all_data({"example": {}})

        self.assertEqual(result.added, {"example": 0})
        self.assertEqual(result.errors[0].scope, "source")
        repository.add_article.assert_not_called()


if __name__ == "__main__":
    unittest.main()
