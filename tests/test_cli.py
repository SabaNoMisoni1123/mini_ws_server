import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server import cli  # noqa: E402
from mini_ws_server.models import UpdateError, UpdateResult  # noqa: E402


class CliTest(unittest.TestCase):
    def tearDown(self):
        package_logger = cli.logging.getLogger("mini_ws_server")
        for handler in list(package_logger.handlers):
            if getattr(handler, cli._HANDLER_MARKER, False):
                package_logger.removeHandler(handler)
                handler.close()

    def _run_main(
        self,
        result: UpdateResult,
        **kwargs,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(cli, "load_site_config", return_value={}),
            patch.object(cli, "MinistrySiteDataGetter") as getter,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            getter.return_value.update_all_data.return_value = result
            exit_code = cli.main(**kwargs)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_default_writes_json_to_stdout_without_creating_log_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "scraper.log"
            with contextlib.chdir(temporary_directory):
                exit_code, stdout, stderr = self._run_main(
                    UpdateResult(added={"site": 2})
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout)["added"], {"site": 2})
        self.assertEqual(stderr, "")
        self.assertFalse(log_path.exists())

    def test_log_file_is_created_only_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "update.log"
            result = UpdateResult(
                errors=[UpdateError("source", "site", "request failed")]
            )
            exit_code, _, stderr = self._run_main(result, log_file=log_path)
            file_log = log_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertIn("Completed with 1 update error(s)", stderr)
        self.assertIn("Completed with 1 update error(s)", file_log)

    def test_log_file_configuration_failure_returns_structured_fatal_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "missing" / "update.log"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = cli.main(log_file=log_path)

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["scope"], "fatal")
        self.assertIn("Fatal logging configuration error", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_partial_failure_returns_one_after_printing_result(self):
        result = UpdateResult(
            added={"failed": 0},
            errors=[UpdateError("source", "failed", "request failed")],
        )

        exit_code, stdout, stderr = self._run_main(result)

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout)["status"], "completed_with_errors")
        self.assertIn("Completed with 1 update error(s)", stderr)

    def test_allow_partial_success_returns_zero(self):
        result = UpdateResult(errors=[UpdateError("source", "failed", "failed")])

        exit_code, stdout, _ = self._run_main(
            result,
            allow_partial_success=True,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout)["status"], "completed_with_errors")

    def test_fatal_error_redacts_secret_and_url_query(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                cli,
                "load_site_config",
                side_effect=RuntimeError(
                    "token=private https://example.test/path?credential=private"
                ),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = cli.main()

        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
        self.assertNotIn("private", combined)
        self.assertIn("[redacted]", combined)


if __name__ == "__main__":
    unittest.main()
