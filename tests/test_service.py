import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
