"""Firestore の情報元別記事データを安全に入出力する運用スクリプト。"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.data_transfer import ArticleDataTransfer  # noqa: E402


HELP_TEXT = "このヘルプを表示して終了します。"
ARGUMENT_GUIDE = """実行形式と実行時引数:
  export --site-id SITE_ID --output OUTPUT_FILE
      --site-id SITE_ID: エクスポートする情報元ID（必須）。
      --output OUTPUT_FILE: 出力する .json または .csv ファイル（必須、既存ファイルは上書き）。
  import SITE_ID INPUT_FILE
      SITE_ID: インポート先の情報元ID（必須）。
      INPUT_FILE: 読み込む .json または .csv ファイル（必須）。
  export-delete --site-id SITE_ID --output OUTPUT_FILE --confirm-delete
      --site-id SITE_ID: エクスポート・削除する情報元ID（必須）。
      --output OUTPUT_FILE: 出力する .json または .csv ファイル（必須、既存ファイルは上書き）。
      --confirm-delete: 削除実行の確認（必須）。"""


def _add_help_option(parser: argparse.ArgumentParser) -> None:
    """日本語のヘルプオプションを追加する。"""
    parser.add_argument("-h", "--help", action="help", help=HELP_TEXT)


def main() -> int:
    """引数に応じてエクスポート、インポート、バックアップ後の削除を実行する。"""
    parser = argparse.ArgumentParser(
        description="情報元ごとの Firestore 記事データを管理します。",
        epilog=ARGUMENT_GUIDE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    _add_help_option(parser)
    commands = parser.add_subparsers(dest="command", required=True, title="利用可能な操作")
    for command, argument_summary in (
        ("export", "--site-id SITE_ID --output OUTPUT_FILE"),
        ("import", "SITE_ID INPUT_FILE"),
        ("export-delete", "--site-id SITE_ID --output OUTPUT_FILE --confirm-delete"),
    ):
        description = {
            "export": "指定した情報元の記事を JSON または CSV ファイルへ出力します。",
            "import": "JSON または CSV ファイルの記事を指定した情報元へ取り込みます。",
            "export-delete": "記事を出力してから、指定した情報元の記事を削除します。",
        }[command]
        subparser = commands.add_parser(
            command,
            help=f"{argument_summary}: {description}",
            description=description,
            add_help=False,
        )
        _add_help_option(subparser)
        if command in {"export", "export-delete"}:
            subparser.add_argument(
                "--site-id", required=True, metavar="SITE_ID", help="対象となる情報元ID。"
            )
            subparser.add_argument(
                "--output",
                type=Path,
                required=True,
                metavar="OUTPUT_FILE",
                help="出力する .json または .csv ファイル。既存ファイルは上書きします。",
            )
        else:
            subparser.add_argument("site_id", metavar="SITE_ID", help="対象となる情報元ID。")
            subparser.add_argument(
                "file", type=Path, metavar="INPUT_FILE", help="入力する .json または .csv ファイル。"
            )
        if command == "export-delete":
            subparser.add_argument(
                "--confirm-delete",
                action="store_true",
                help="削除を実行することを明示的に確認します。",
            )
    args = parser.parse_args()

    if args.command == "export-delete" and not args.confirm_delete:
        parser.error("export-delete requires --confirm-delete")

    from mini_ws_server.repositories.firestore import FirestoreRepository

    transfer = ArticleDataTransfer(FirestoreRepository())
    if args.command == "export":
        print(f"Exported {transfer.export_articles(args.site_id, args.output)} articles.")
    elif args.command == "import":
        added, skipped = transfer.import_articles(args.site_id, args.file)
        print(f"Imported {added} articles; skipped {skipped} existing articles.")
    else:
        print(f"Exported and deleted {transfer.export_and_delete_articles(args.site_id, args.output)} articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
