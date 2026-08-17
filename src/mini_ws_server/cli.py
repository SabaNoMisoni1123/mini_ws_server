"""本番更新処理のコマンドライン入口。"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import SOURCES_PATH, load_site_config
from .models import UpdateError, UpdateResult, safe_error_message
from .service import MinistrySiteDataGetter


LOGGER = logging.getLogger(__name__)
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
_HANDLER_MARKER = "_mini_ws_server_cli_handler"


def _positive_int(value: str) -> int:
    """正の整数を引数として受け付ける。"""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("正の整数を指定してください") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください")
    return parsed


def configure_logging(log_level: str = "INFO", log_file: Path | None = None) -> None:
    """CLI 用ログを標準エラーと、任意のファイルへ設定する。"""
    package_logger = logging.getLogger("mini_ws_server")
    for handler in list(package_logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            package_logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _HANDLER_MARKER, True)
        package_logger.addHandler(handler)
    package_logger.setLevel(getattr(logging, log_level))
    package_logger.propagate = False


def _fatal_result(error: Exception) -> UpdateResult:
    """致命的な例外を安全な構造化結果へ変換する。"""
    return UpdateResult(
        errors=[
            UpdateError(
                scope="fatal",
                source_id=None,
                message=safe_error_message(error),
            )
        ]
    )


def _print_result(result: UpdateResult) -> None:
    """更新結果を標準出力へ JSON として出力する。"""
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def main(
    days_range: int = 3,
    log_file: Path | None = None,
    log_level: str = "INFO",
    allow_partial_success: bool = False,
) -> int:
    """サイト定義を読み込み、全サイトの新着情報を更新する。"""
    try:
        configure_logging(log_level=log_level, log_file=log_file)
    except Exception as exc:
        print(
            f"Fatal logging configuration error ({type(exc).__name__})",
            file=sys.stderr,
        )
        _print_result(_fatal_result(exc))
        return 1

    try:
        site_dict = load_site_config(SOURCES_PATH)
        scraper = MinistrySiteDataGetter()
        result = scraper.update_all_data(site_dict, days=days_range)
    except Exception as exc:
        LOGGER.error("Fatal error (%s)", type(exc).__name__)
        result = _fatal_result(exc)
        _print_result(result)
        return 1

    _print_result(result)
    if result.errors:
        LOGGER.error("Completed with %s update error(s)", len(result.errors))
    return 0 if result.success or allow_partial_success else 1


def command_line_main(argv: list[str] | None = None) -> int:
    """コマンドライン引数を解釈して本番更新を実行する。"""
    parser = argparse.ArgumentParser(
        description="全情報元の新着情報を取得し、Firestore を更新します。"
    )
    parser.add_argument(
        "--days-range",
        type=_positive_int,
        default=3,
        metavar="N",
        help="確認する過去の日数（実行日を基準、既定値: 3）。",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        metavar="PATH",
        help="指定した場合だけ、標準エラーと同じログをファイルにも保存します。",
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS,
        default="INFO",
        help="ログレベル（既定値: %(default)s）。",
    )
    parser.add_argument(
        "--allow-partial-success",
        action="store_true",
        help="部分失敗があっても終了コード 0 を返します。",
    )
    args = parser.parse_args(argv)
    return main(
        days_range=args.days_range,
        log_file=args.log_file,
        log_level=args.log_level,
        allow_partial_success=args.allow_partial_success,
    )
