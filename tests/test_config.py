import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.config import SOURCES_PATH, load_site_config  # noqa: E402


class SiteConfigTest(unittest.TestCase):
    def test_sources_file_has_required_keys(self):
        sources = load_site_config(SOURCES_PATH)

        self.assertTrue(sources)
        for site_id, config in sources.items():
            with self.subTest(site_id=site_id):
                self.assertTrue({"name", "url", "useDefaultFunc", "arg"} <= config.keys())
                if config["useDefaultFunc"] is False:
                    self.assertIn("funcID", config)


if __name__ == "__main__":
    unittest.main()
