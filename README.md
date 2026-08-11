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

Firestore を使用する実行には、サービスアカウント JSON のパスを `FIREBASE_ADMIN_SDK` 環境変数で指定します。認証情報はリポジトリに追加しないでください。

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
python scripts/run.py partial-update --help
```

利用できる操作は次のとおりです。

| 操作 | 実行例 | 動作 |
| --- | --- | --- |
| `update` | `python scripts/run.py update` | 全情報元の新着情報を取得し、Firestore を更新します。 |
| `check-source` | `python scripts/run.py check-source <site_id>` | `checkUrlList.json` の候補を1件取得して、保存せずに解析結果を表示します。`site_id` を省略すると先頭の候補を使います。 |
| `add-source` | `python scripts/run.py add-source` | 候補設定にのみある情報元を Firestore のサイト一覧へ追加します。 |
| `partial-update` | `python scripts/run.py partial-update --exclude-site-id metiShingikai --output result.json` | 指定情報元を除外して取得し、結果をローカル JSON に保存します。既定の出力先は `sample.json` です。 |
| `export` | `python scripts/run.py export <site_id> backup.json` | 指定情報元の記事を JSON または CSV にエクスポートします。既存ファイルは上書きしません。 |
| `import` | `python scripts/run.py import <site_id> backup.csv` | JSON または CSV の記事を、既存の `hash` を除外して Firestore に追加します。 |
| `export-delete` | `python scripts/run.py export-delete <site_id> backup.json --confirm-delete` | エクスポート成功後に、指定情報元の記事コレクションを削除します。削除確認オプションが必須です。 |

`update`、`add-source`、`import`、`export-delete` は Firestore を変更します。`update`、
`check-source`、`partial-update` は外部サイトへアクセスします。実行前に対象と認証情報を確認してください。

## 従来の実行方法

```bash
python main.py
# または、pip install -e . の後
mini-ws-update
```

候補サイトを確認するには、ローカル専用の `checkUrlList.json` を用意してから実行します。

```bash
python scripts/check_source.py <site_id>
python scripts/add_source.py
```

これらのコマンドは外部サイトやFirestoreへアクセスするため、明示的に必要な場合だけ実行してください。

## 情報元別データの入出力

記事データは情報元 ID を指定して JSON または CSV にエクスポートできます。インポートでは
`hash` が既に Firestore にある記事を更新せずにスキップします。

```bash
python scripts/manage_site_data.py export <site_id> backup.json
python scripts/manage_site_data.py import <site_id> backup.csv
python scripts/manage_site_data.py export-delete <site_id> backup.json --confirm-delete
```

出力ファイルが既にある場合は事故防止のため失敗します。`export-delete` はエクスポートが成功して
から指定情報元の**記事コレクションだけ**を削除します。`siteData` の情報元一覧や設定ファイルは削除しません。

## テスト

```bash
python -m unittest discover -s tests
```

テストは fixture と fake リポジトリだけを使い、ネットワークおよび Firestore に接続しません。
