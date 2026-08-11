import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from mini_ws_server.scrapers.generic_html import scrape  # noqa: E402

    HTML_DEPENDENCIES_AVAILABLE = True
except ModuleNotFoundError:
    HTML_DEPENDENCIES_AVAILABLE = False


class FakeResponse:
    text = (PROJECT_ROOT / "tests/fixtures/html/generic_news.html").read_text(
        encoding="utf-8"
    )

    def raise_for_status(self):
        return None


@unittest.skipUnless(HTML_DEPENDENCIES_AVAILABLE, "requests と beautifulsoup4 が必要です")
class GenericHtmlScraperTest(unittest.TestCase):
    @patch("mini_ws_server.scrapers.generic_html.requests.get", return_value=FakeResponse())
    def test_scrape_builds_article(self, request_get):
        items = scrape(
            "https://example.test/news",
            "Example",
            {
                "dataListPath": "#items",
                "dateFormat": "%Y-%m-%d",
                "path": {"url": "article", "title": "h2", "date": "time"},
            },
        )

        self.assertEqual(request_get.call_args.kwargs["timeout"], 20)
        self.assertEqual(items[0]["url"], "https://example.test/one")
        self.assertEqual(items[0]["title"], "First")
        self.assertEqual(items[0]["org"], "Example")
        self.assertEqual(len(items[0]["hash"]), 64)


if __name__ == "__main__":
    unittest.main()
