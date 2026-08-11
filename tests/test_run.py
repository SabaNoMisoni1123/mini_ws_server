import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run


class RunScriptTest(unittest.TestCase):
    def test_export_help_identifies_each_required_argument(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                run.main(["export", "--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("--site-id SITE_ID", help_text)
        self.assertIn("--output OUTPUT_FILE", help_text)
        self.assertIn("対象となる情報元ID。", help_text)
        self.assertIn("出力する .json または .csv ファイル。", help_text)

    def test_top_level_help_lists_command_signatures_and_argument_meanings(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                run.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("export --site-id SITE_ID --output OUTPUT_FILE", help_text)
        self.assertIn("import SITE_ID INPUT_FILE", help_text)
        self.assertIn("--confirm-delete: 削除実行の確認（必須）。", help_text)
        self.assertIn("-h, --help", help_text)
        self.assertIn("このヘルプを表示して終了します。", help_text)

    def test_update_delegates_to_existing_update_cli(self):
        with patch.object(run.cli, "main", return_value=0) as update_main:
            exit_code = run.main(["update"])

        self.assertEqual(exit_code, 0)
        update_main.assert_called_once_with()

    def test_check_source_uses_requested_candidate(self):
        sources = {"candidate": {"name": "候補"}}
        with (
            patch.object(run, "load_site_config", return_value=sources),
            patch.object(run, "MinistrySiteDataGetter") as getter,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = run.main(["check-source", "candidate"])

        self.assertEqual(exit_code, 0)
        getter.return_value.test_new_source.assert_called_once_with("candidate", sources["candidate"])

    def test_partial_update_arguments_are_parsed(self):
        output = Path("result.json")
        with patch.object(run, "_partial_update", return_value=0) as partial_update:
            exit_code = run.main(
                ["partial-update", "--exclude-site-id", "site-a", "--output", str(output)]
            )

        self.assertEqual(exit_code, 0)
        partial_update.assert_called_once_with("site-a", output)

    def test_list_shows_site_id_and_overview(self):
        sources = {
            "site-b": {"name": "サイトB", "url": "https://b.example.test"},
            "site-a": {"name": "サイトA", "url": "https://a.example.test"},
        }
        output = io.StringIO()
        with (
            patch.object(run, "load_site_config", return_value=sources),
            contextlib.redirect_stdout(output),
        ):
            exit_code = run.main(["list"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "site_id\tname\turl",
                "site-a\tサイトA\thttps://a.example.test",
                "site-b\tサイトB\thttps://b.example.test",
            ],
        )

    def test_export_delete_requires_explicit_confirmation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                run.main(
                    [
                        "export-delete",
                        "--site-id",
                        "site-a",
                        "--output",
                        "backup.json",
                    ]
                )

        self.assertEqual(raised.exception.code, 2)

    def test_export_uses_required_named_arguments(self):
        output = Path("backup.json")
        with patch.object(run, "_manage_articles", return_value=0) as manage_articles:
            exit_code = run.main(["export", "--site-id", "site-a", "--output", str(output)])

        self.assertEqual(exit_code, 0)
        args = manage_articles.call_args.args[0]
        self.assertEqual(args.site_id, "site-a")
        self.assertEqual(args.output, output)

    def test_export_rejects_positional_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                run.main(["export", "site-a", "backup.json"])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
