"""Firestore の情報元別記事データを安全に入出力する運用スクリプト。"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.data_transfer import ArticleDataTransfer  # noqa: E402


def main() -> int:
    """引数に応じてエクスポート、インポート、バックアップ後の削除を実行する。"""
    parser = argparse.ArgumentParser(description="情報元ごとの Firestore 記事データを管理します。")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "import", "export-delete"):
        subparser = commands.add_parser(command)
        subparser.add_argument("site_id")
        subparser.add_argument("file", type=Path)
        if command == "export-delete":
            subparser.add_argument("--confirm-delete", action="store_true")
    args = parser.parse_args()

    if args.command == "export-delete" and not args.confirm_delete:
        parser.error("export-delete requires --confirm-delete")

    from mini_ws_server.repositories.firestore import FirestoreRepository

    transfer = ArticleDataTransfer(FirestoreRepository())
    if args.command == "export":
        print(f"Exported {transfer.export_articles(args.site_id, args.file)} articles.")
    elif args.command == "import":
        added, skipped = transfer.import_articles(args.site_id, args.file)
        print(f"Imported {added} articles; skipped {skipped} existing articles.")
    else:
        print(f"Exported and deleted {transfer.export_and_delete_articles(args.site_id, args.file)} articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
