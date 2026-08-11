import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run


class RunScriptTest(unittest.TestCase):
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

    def test_export_delete_requires_explicit_confirmation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                run.main(["export-delete", "site-a", "backup.json"])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
