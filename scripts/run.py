"""プロジェクトの運用機能をまとめて呼び出すコマンドラインラッパー。"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server import cli  # noqa: E402
from mini_ws_server.config import CHECK_SOURCES_PATH, SOURCES_PATH, load_site_config  # noqa: E402
from mini_ws_server.data_transfer import ArticleDataTransfer  # noqa: E402
from mini_ws_server.service import MinistrySiteDataGetter  # noqa: E402
from mini_ws_server.source_sync import SourceSyncError, SourceSynchronizer  # noqa: E402


HELP_TEXT = "このヘルプを表示して終了します。"
RUN_ARGUMENT_GUIDE = """実行形式と実行時引数:
  update
      [--days-range N] [--log-file PATH] [--log-level LEVEL]
      [--credential-path PATH] [--allow-partial-success]。すべての有効な情報元を更新します。
      --days-range N: 確認する過去の日数（実行日を含む、既定値: 3）。
      --log-file PATH: 指定時だけログをファイルにも保存します。
      --log-level LEVEL: DEBUG、INFO、WARNING、ERROR（既定値: INFO）。
      --credential-path PATH: ローカルの Firebase サービスアカウント JSON。
          省略時は環境変数などの Application Default Credentials を使用します。
      --allow-partial-success: 部分失敗があっても終了コード0を返します。
  check-source [SITE_ID]
      SITE_ID: 確認する候補情報元のID。省略時は先頭の候補を使用します。
  add-source
      引数なし。候補設定にのみある情報元を追加します。
  list
      引数なし。利用可能な情報元のID、名称、URLを表示します。
  partial-update [--exclude-site-id SITE_ID] [--output OUTPUT_FILE]
      --days-range N: 確認する過去の日数（実行日を含む、既定値: 3）。
      --exclude-site-id SITE_ID: 更新対象から除外する情報元ID（既定値: metiShingikai）。
      --output OUTPUT_FILE: 結果を書き出すJSONファイル（既定値: sample.json）。
  export --site-id SITE_ID --output OUTPUT_FILE
      --site-id SITE_ID: エクスポートする情報元ID（必須）。
      --output OUTPUT_FILE: 出力する .json または .csv ファイル（必須、既存ファイルは上書き）。
  import SITE_ID INPUT_FILE
      SITE_ID: インポート先の情報元ID（必須）。
      INPUT_FILE: 読み込む .json または .csv ファイル（必須）。
  export-delete --site-id SITE_ID --output OUTPUT_FILE --confirm-delete
      --site-id SITE_ID: エクスポート・削除する情報元ID（必須）。
      --output OUTPUT_FILE: 出力する .json または .csv ファイル（必須、既存ファイルは上書き）。
      --confirm-delete: 削除実行の確認（必須）。
  sync-sources [--apply] [--confirm-delete] [--backup-dir DIR] [--overwrite-backup]
      --apply: 差分を Firestore に反映します。省略時は dry-run です。
      --confirm-delete: 削除対象を反映する場合の確認です。
      --backup-dir DIR: 削除対象の記事バックアップ先です。
      --overwrite-backup: 既存バックアップの上書きを許可します。"""


def _add_help_option(parser: argparse.ArgumentParser) -> None:
    """日本語のヘルプオプションを追加する。"""
    parser.add_argument("-h", "--help", action="help", help=HELP_TEXT)


def build_parser() -> argparse.ArgumentParser:
    """統一ラッパー用の引数パーサーを作成する。"""
    parser = argparse.ArgumentParser(
        prog="python scripts/run.py",
        description=(
            "官公庁用ウェブスクレイパーの更新・候補確認・記事データ管理を実行します。\n"
            "各操作の詳細は `python scripts/run.py <command> --help` で確認できます。"
        ),
        epilog=RUN_ARGUMENT_GUIDE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    _add_help_option(parser)
    commands = parser.add_subparsers(dest="command", required=True, title="利用可能な操作")

    update = commands.add_parser(
        "update",
        help="引数なし: 全ての有効な情報元を取得し、Firestore を更新します。",
        description="config/sources.json の全情報元を取得し、新着記事を Firestore に追加します。",
        add_help=False,
    )
    _add_help_option(update)
    update.add_argument(
        "--days-range",
        type=cli._positive_int,
        default=3,
        metavar="N",
        help="確認する過去の日数（実行日を基準、既定値: 3）。",
    )
    update.add_argument(
        "--log-file",
        type=Path,
        metavar="PATH",
        help="指定した場合だけ、標準エラーと同じログをファイルにも保存します。",
    )
    update.add_argument(
        "--log-level",
        choices=cli.LOG_LEVELS,
        default="INFO",
        help="ログレベル（既定値: %(default)s）。",
    )
    update.add_argument(
        "--credential-path",
        type=Path,
        metavar="PATH",
        help=(
            "ローカルの Firebase サービスアカウント JSON。省略時は "
            "GOOGLE_APPLICATION_CREDENTIALS などの Application Default Credentials を使用します。"
        ),
    )
    update.add_argument(
        "--allow-partial-success",
        action="store_true",
        help="部分失敗があっても終了コード 0 を返します。",
    )

    check_source = commands.add_parser(
        "check-source",
        help="[SITE_ID]: 候補情報元を1件取得して解析結果を表示します。",
        description=(
            "checkUrlList.json の候補情報元を取得し、Firestore へ保存せず解析結果を表示します。"
        ),
        add_help=False,
    )
    _add_help_option(check_source)
    check_source.add_argument(
        "site_id",
        nargs="?",
        metavar="SITE_ID",
        help="確認する候補情報元のID。省略時は設定ファイルの先頭の候補を使用します。",
    )

    add_source = commands.add_parser(
        "add-source",
        help="引数なし: 候補情報元を Firestore のサイト一覧へ追加します。",
        description=(
            "checkUrlList.json にあって config/sources.json にない情報元を Firestore のサイト一覧へ追加します。"
        ),
        add_help=False,
    )
    _add_help_option(add_source)

    list_sources = commands.add_parser(
        "list",
        help="引数なし: 利用可能な情報元のIDと概要を一覧表示します。",
        description="config/sources.json の情報元ID、名称、URLを一覧表示します。",
        add_help=False,
    )
    _add_help_option(list_sources)

    partial_update = commands.add_parser(
        "partial-update",
        help="[--exclude-site-id SITE_ID] [--output OUTPUT_FILE]: 更新結果をローカル JSON に保存します。",
        description="Firestore へ保存せず、取得結果をローカルファイルへ保存する確認用の更新です。",
        add_help=False,
    )
    _add_help_option(partial_update)
    partial_update.add_argument(
        "--days-range",
        type=cli._positive_int,
        default=3,
        metavar="N",
        help="確認する過去の日数（実行日を基準、既定値: 3）。",
    )
    partial_update.add_argument(
        "--exclude-site-id",
        default="metiShingikai",
        metavar="SITE_ID",
        help="更新対象から除外するサイトID（既定値: metiShingikai）。",
    )
    partial_update.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "sample.json",
        metavar="OUTPUT_FILE",
        help="更新結果の出力先 JSON ファイル（既定値: %(default)s）。既存ファイルは上書きします。",
    )

    sync_sources = commands.add_parser(
        "sync-sources",
        help="[--apply] [--confirm-delete]: sources.json と Firestore の情報元一覧を同期します。",
        description=(
            "config/sources.json を正として Firestore の siteData と比較します。"
            "既定は変更を行わない dry-run です。"
        ),
        add_help=False,
    )
    _add_help_option(sync_sources)
    sync_sources.add_argument(
        "--apply",
        action="store_true",
        help="追加・更新・削除を Firestore に反映します。",
    )
    sync_sources.add_argument(
        "--confirm-delete",
        action="store_true",
        help="削除対象がある場合、その削除を明示的に確認します。",
    )
    sync_sources.add_argument(
        "--backup-dir",
        type=Path,
        metavar="DIR",
        help="削除する記事のバックアップ先（既定値: ./backup-YYYY-MM-DD）。",
    )
    sync_sources.add_argument(
        "--overwrite-backup",
        action="store_true",
        help="同名の既存バックアップファイルを上書きします。",
    )

    for command, help_text, description in (
        ("export", "情報元の記事を JSON または CSV にエクスポートします。", "Firestore の記事をファイルへ保存します。"),
        ("import", "JSON または CSV の記事を重複なしでインポートします。", "ファイルの記事を Firestore に追加します。"),
        (
            "export-delete",
            "記事をエクスポート後、Firestore から削除します。",
            "エクスポート成功後、指定情報元の記事コレクションを削除します。",
        ),
    ):
        argument_summary = {
            "export": "--site-id SITE_ID --output OUTPUT_FILE",
            "import": "SITE_ID INPUT_FILE",
            "export-delete": "--site-id SITE_ID --output OUTPUT_FILE --confirm-delete",
        }[command]
        data_command = commands.add_parser(
            command,
            help=f"{argument_summary}: {help_text}",
            description=description,
            add_help=False,
        )
        _add_help_option(data_command)
        if command in {"export", "export-delete"}:
            data_command.add_argument(
                "--site-id",
                required=True,
                metavar="SITE_ID",
                help="対象となる情報元ID。",
            )
            data_command.add_argument(
                "--output",
                type=Path,
                required=True,
                metavar="OUTPUT_FILE",
                help="出力する .json または .csv ファイル。既存ファイルは上書きします。",
            )
        else:
            data_command.add_argument(
                "site_id", metavar="SITE_ID", help="対象となる情報元ID。"
            )
            data_command.add_argument(
                "file", type=Path, metavar="INPUT_FILE", help="入力する .json または .csv ファイル。"
            )
        if command == "export-delete":
            data_command.add_argument(
                "--confirm-delete",
                action="store_true",
                help="削除を実行することを明示的に確認します。",
            )

    return parser


def _check_source(site_id: str | None) -> int:
    sources = load_site_config(CHECK_SOURCES_PATH)
    selected_site_id = site_id or next(iter(sources), None)
    if selected_site_id is None or selected_site_id not in sources:
        raise RuntimeError(f"Unknown site_id: {selected_site_id}")
    print(selected_site_id)
    print(MinistrySiteDataGetter().test_new_source(selected_site_id, sources[selected_site_id]))
    return 0


def _add_source() -> int:
    sources = load_site_config(SOURCES_PATH)
    candidates = load_site_config(CHECK_SOURCES_PATH)
    new_sources = {key: value for key, value in candidates.items() if key not in sources}
    for site_id in new_sources:
        print(f"New source: {site_id}")
    added = MinistrySiteDataGetter().add_site(new_sources)
    print(f"Added sites: {added}")
    return 0


def _list_sources() -> int:
    """有効な情報元のID、名称、URLを表示する。"""
    sources = load_site_config(SOURCES_PATH)
    print("site_id\tname\turl")
    for site_id, config in sorted(sources.items()):
        print(f"{site_id}\t{config['name']}\t{config['url']}")
    return 0


def _partial_update(exclude_site_id: str, output: Path, days_range: int = 3) -> int:
    sources = load_site_config(SOURCES_PATH)
    sources.pop(exclude_site_id, None)
    result = MinistrySiteDataGetter().update_all_data(sources, days=days_range)
    record = {
        "ws_result": result.to_dict(),
        "timestamp": datetime.now().strftime("%m/%d %H:%M:%S"),
    }
    output.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    print(f"Saved update result to {output}")
    return 0


def _manage_articles(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
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
        count = transfer.export_and_delete_articles(args.site_id, args.output)
        print(f"Exported and deleted {count} articles.")
    return 0


def _sync_sources(args: argparse.Namespace) -> int:
    """sources.json と Firestore の siteData の差分を確認・反映する。"""
    from mini_ws_server.repositories.firestore import FirestoreRepository

    sources = load_site_config(SOURCES_PATH)
    synchronizer = SourceSynchronizer(
        FirestoreRepository(),
        config_path=SOURCES_PATH,
    )
    try:
        result = synchronizer.synchronize(
            sources,
            apply=args.apply,
            confirm_delete=args.confirm_delete,
            backup_dir=args.backup_dir,
            overwrite_backup=args.overwrite_backup,
        )
    except SourceSyncError as exc:
        print(f"同期を中止しました: {exc}", file=sys.stderr)
        return 1
    return 0 if result.success else 1


def main(argv: list[str] | None = None) -> int:
    """指定された操作を実行する。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "update":
        return cli.main(
            days_range=args.days_range,
            log_file=args.log_file,
            log_level=args.log_level,
            allow_partial_success=args.allow_partial_success,
            credential_path=args.credential_path,
        )
    if args.command == "check-source":
        return _check_source(args.site_id)
    if args.command == "add-source":
        return _add_source()
    if args.command == "list":
        return _list_sources()
    if args.command == "partial-update":
        if args.days_range == 3:
            return _partial_update(args.exclude_site_id, args.output)
        return _partial_update(args.exclude_site_id, args.output, args.days_range)
    if args.command == "sync-sources":
        return _sync_sources(args)
    return _manage_articles(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
