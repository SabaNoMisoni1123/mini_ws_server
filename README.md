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

## 実行

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
