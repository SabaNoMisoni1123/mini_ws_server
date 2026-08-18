# 官公庁用ウェブスクレイパー

官公庁サイトの HTML/RSS から新着情報を取得し、Firestore に追加する Python ツールです。

## 構成

- `src/mini_ws_server/`: アプリケーション本体
- `config/sources.json`: 更新対象のサイト定義
- `config/disabled_sources.json`: 使用しないサイト定義
- `scripts/`: 明示的に実行する保守スクリプト
- `tests/`: 外部サービスを使わない自動テスト
- ルートの `main.py`、`wslib.py`、`funclib.py`: 旧利用者向けの互換入口

## セットアップ

```bash
pip install -r requirements.txt
```

パッケージとして使用する場合は、開発用に次のようにインストールできます。

```bash
pip install -e .
```

Firestore を使用する実行は Google Application Default Credentials（ADC）で認証します。
GitHub Actions では、ワークフローが Secret から一時ファイルを作成し、`GOOGLE_APPLICATION_CREDENTIALS` を設定します。
ローカルでは `update` の `--credential-path` にサービスアカウント JSON を指定できます。フラグを省略した場合、互換用の `FIREBASE_ADMIN_SDK` が設定されていればそのパスを使い、未設定なら `GOOGLE_APPLICATION_CREDENTIALS` を含む実行環境の ADC を利用します。認証情報はリポジトリに追加しないでください。

```bash
pipenv run python scripts/run.py update --credential-path "C:\\path\\to\\firebase-service-account.json"
```

環境変数を使う場合は、従来どおり次の形式でも実行できます。

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\firebase-service-account.json"
pipenv run python scripts/run.py update
```

GitHub Actions の初期設定と手動確認は
[`docs/github-actions-update-setup.md`](docs/github-actions-update-setup.md) を参照してください。

## 統一コマンドによる実行

`scripts/run.py` は、本プロジェクトの運用機能を一つにまとめたラッパースクリプトです。
まず全操作の一覧を確認できます。

```bash
python scripts/run.py --help
# 短縮形
python scripts/run.py -h
```

各操作の引数、既定値、副作用は、操作名の後ろに `--help`（または `-h`）を付けて確認します。

```bash
python scripts/run.py update --help
```

利用できる操作は次のとおりです。

| 操作 | 実行例 | 動作 |
| --- | --- | --- |
| `update` | `python scripts/run.py update [--days-range 3]` | 指定した日数の範囲で全情報元の新着情報を取得し、Firestore を更新します。`--days-range` の既定値は3です。 |
| `check-source` | `python scripts/run.py check-source <site_id>` | `checkUrlList.json` の候補を1件取得して、保存せずに解析結果を表示します。`site_id` を省略すると先頭の候補を使います。 |
| `add-source` | `python scripts/run.py add-source` | 候補設定にのみある情報元を Firestore のサイト一覧へ追加します。 |
| `list` | `python scripts/run.py list` | 利用可能な情報元のID、名称、URLを一覧表示します。`export` などで指定する `site_id` の確認に使えます。 |
| `partial-update` | `python scripts/run.py partial-update --days-range 3 --exclude-site-id metiShingikai --output result.json` | 指定日数の範囲で情報元を除外して取得し、結果をローカル JSON に保存します。既定の出力先は `sample.json` です。 |
| `export` | `python scripts/run.py export --site-id <site_id> --output backup.json` | 指定情報元の記事を JSON または CSV にエクスポートします。既存ファイルは上書きします。 |
| `import` | `python scripts/run.py import <site_id> backup.csv` | JSON または CSV の記事を、既存の `hash` を除外して Firestore に追加します。 |
| `export-delete` | `python scripts/run.py export-delete --site-id <site_id> --output backup.json --confirm-delete` | エクスポート成功後に、指定情報元の記事コレクションを削除します。削除確認オプションが必須です。 |
| `sync-sources` | `python scripts/run.py sync-sources` | `config/sources.json` と Firestore の `siteData` の差分を表示します。既定は dry-run です。 |

`update`、`add-source`、`import`、`export-delete`、`sync-sources --apply` は Firestore を変更します。`update`、
`check-source`、`partial-update` は外部サイトへアクセスします。実行前に対象と認証情報を確認してください。

## 情報元設定と Firestore の同期

`config/sources.json` を情報元一覧の正として、Firestore の `siteData` を追加・更新・削除できます。
まず dry-run で、追加・更新・再採番・削除の計画を確認してください。

```bash
python scripts/run.py sync-sources
python scripts/run.py sync-sources --apply
```

削除対象がある適用では `--confirm-delete` が必須です。削除対象の記事はすべて JSON に保存して
再読込検証した後にだけ削除されます。既定の保存先は実行日の
`./backup-YYYY-MM-DD` で、`--backup-dir DIR` でも指定できます。

```bash
python scripts/run.py sync-sources --apply --confirm-delete
python scripts/run.py sync-sources --apply --confirm-delete --backup-dir /path/to/backup
```

バックアップ先に同名の記事 JSON または `manifest.json` がある場合は停止します。意図して
上書きする場合に限り `--overwrite-backup` を追加してください。削除途中で失敗した情報元は
`siteData` 文書を残し、検証済みバックアップと `manifest.json` に結果を記録します。

## 従来の実行方法

```bash
python main.py
# または、pip install -e . の後
mini-ws-update
```

更新ログは標準エラー、最終結果 JSON は標準出力へ出力されます。部分失敗時は、残りの情報元を
処理した後に終了コード `1` を返します。必要な場合だけログファイルや互換動作を明示できます。

```bash
python scripts/run.py update --log-level DEBUG --log-file scraper.log
python scripts/run.py update --allow-partial-success
```

候補サイトを確認するには、ローカル専用の `checkUrlList.json` を用意してから実行します。

```bash
python scripts/check_source.py <site_id>
python scripts/add_source.py
```

これらのコマンドは外部サイトやFirestoreへアクセスするため、明示的に必要な場合だけ実行してください。

## 情報元別データの入出力

記事データは情報元 ID を指定して JSON または CSV にエクスポートできます。エクスポートする
すべての記事には、URL・タイトル・日時から生成した一意な `hash` を必ず含めます。インポートでは
この `hash` が既に Firestore にある記事を更新せずにスキップします。バックアップファイルから
`hash` を削除または変更すると、重複判定できなくなるため編集しないでください。

```bash
python scripts/manage_site_data.py export --site-id <site_id> --output backup.json
python scripts/manage_site_data.py import <site_id> backup.csv
python scripts/manage_site_data.py export-delete --site-id <site_id> --output backup.json --confirm-delete
```

出力ファイルが既にある場合は上書きします。`export-delete` はエクスポートが成功して
から指定情報元の**記事コレクションだけ**を削除します。`siteData` の情報元一覧や設定ファイルは削除しません。

## テスト

```bash
python -m unittest discover -s tests
```

テストは fixture と fake リポジトリだけを使い、ネットワークおよび Firestore に接続しません。
