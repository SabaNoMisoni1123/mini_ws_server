import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server import cli  # noqa: E402


class CliTest(unittest.TestCase):
    def test_main_creates_log_file_in_current_working_directory(self):
        """ログ出力先は実行時のカレントディレクトリになる。"""
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            os.chdir(temporary_directory)
            try:
                with (
                    patch.object(cli.logging, "basicConfig") as basic_config,
                    patch.object(cli.logging, "FileHandler") as file_handler,
                    patch.object(cli, "load_site_config", return_value={}),
                    patch.object(cli, "MinistrySiteDataGetter") as getter,
                ):
                    getter.return_value.update_all_data.return_value = {}
                    getter.return_value.errors = []

                    exit_code = cli.main()
            finally:
                os.chdir(previous_directory)

        self.assertEqual(exit_code, 0)
        file_handler.assert_called_once_with(
            Path(temporary_directory) / "scraper.log", encoding="utf-8"
        )
        self.assertTrue(basic_config.called)


if __name__ == "__main__":
    unittest.main()
