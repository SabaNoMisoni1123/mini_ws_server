import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server import cli  # noqa: E402


class CliCredentialsTest(unittest.TestCase):
    @patch("mini_ws_server.cli.load_site_config", return_value={})
    @patch("mini_ws_server.cli.MinistrySiteDataGetter")
    def test_main_passes_explicit_credential_path(self, getter_class, load_config):
        credential_path = Path("credentials/firebase.json")
        getter_class.return_value.update_all_data.return_value = Mock(
            success=True,
            errors=[],
            to_dict=lambda: {"success": True, "added": {}, "errors": []},
        )

        result = cli.main(credential_path=credential_path)

        self.assertEqual(result, 0)
        getter_class.assert_called_once_with(credential_path=credential_path)

    @patch("mini_ws_server.cli.main", return_value=0)
    def test_command_line_accepts_credential_path(self, main):
        result = cli.command_line_main(
            ["--credential-path", "credentials/firebase.json"]
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            main.call_args.kwargs["credential_path"],
            Path("credentials/firebase.json"),
        )


if __name__ == "__main__":
    unittest.main()
