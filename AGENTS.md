# AGENTS.md

## この文書の目的

このリポジトリで作業する人間・AI向けの共通ガイドです。変更前に実ファイルを確認し、現在の動作を保ってください。新規実装は `src/mini_ws_server/` に置き、ルート直下へ責務を増やしません。

## プロジェクト概要

官公庁サイトの HTML/RSS から新着情報を取得し、重複と期間を判定して Firestore に追加する Python ユーティリティです。

主要な責務は次のとおりです。

- `src/mini_ws_server/cli.py`: 本番更新処理の入口。
- `src/mini_ws_server/service.py`: 取得、重複判定、保存を調整するユースケース。
- `src/mini_ws_server/scrapers/`: 汎用 HTML/RSS とサイト固有の解析。
- `src/mini_ws_server/repositories/firestore.py`: Firestore アクセス。
- `config/sources.json`: 使用中のサイト定義。
- `config/disabled_sources.json`: 使用しないサイト定義。
- `scripts/`: 候補ソースの確認・追加など、明示的に実行する運用処理。
- ルートの `main.py`、`wslib.py`、`funclib.py`、`add_new_source.py`、`check_new_source.py`、`script1.py`: 旧コマンド・import 向けの互換入口。新規コードからは使わない。

`add_new_source.py` と `check_new_source.py` が参照する `checkUrlList.json` は `.gitignore` 対象で、通常はローカルにだけ存在します。

## 標準フォルダ構成

新規コードは次の構成に置きます。無関係な移動や互換入口の削除は行いません。

```text
mini_ws_server/
├── pyproject.toml                 # パッケージ定義と実行コマンド
├── README.md
├── AGENTS.md
├── config/
│   ├── sources.json
│   └── disabled_sources.json
├── src/
│   └── mini_ws_server/
│       ├── __init__.py
│       ├── cli.py                 # CLI の入口
│       ├── config.py              # 設定読込・検証
│       ├── models.py              # 記事・サイト設定の型
│       ├── service.py             # 取得→絞込→保存のユースケース
│       ├── scrapers/
│       │   ├── base.py            # 共通インターフェース
│       │   ├── generic_html.py
│       │   ├── generic_feed.py
│       │   └── ministries.py      # サイト固有パーサー
│       └── repositories/
│           └── firestore.py       # Firestore の読み書き
├── scripts/
│   ├── add_source.py
│   ├── check_source.py
│   └── partial_update.py
└── tests/
    ├── fixtures/
    │   ├── html/
    │   ├── feeds/
    │   └── sources/
    ├── test_config.py
    ├── test_generic_html.py
    └── test_service.py
```

責務の依存方向は `cli → service → scrapers/repositories` とし、スクレイパーから Firestore を直接呼びません。サイト固有処理は `scrapers/` に閉じ込め、設定読込、HTTP取得、HTML/RSS解析、保存処理を分離します。

## 構成変更時の判断

- 解析ロジックは `scrapers/`、DBの読み書きは `repositories/`、両者を組み合わせる処理は `service.py` に置く。
- CLI 引数・ログ設定は `cli.py`、JSONファイルの場所と読込検証は `config.py` に置く。
- 運用専用の処理は `scripts/` に置き、アプリケーション本体から import しない。
- 新たなルート直下の Python ファイルは原則として作らない。互換入口が不要になった場合の削除は、利用者への周知を含む別変更にする。
- 構成移動では import、設定パス、README、CI、テストを同じ変更で更新する。

## 開発・実行コマンド

依存モジュールは Pipenv の仮想環境で管理しています。リポジトリルートから
Python スクリプトやテストを実行するときは、仮想環境の依存を確実に使用するため
`python` ではなく `pipenv run python` を用います。依存環境が未作成の場合は、先に
`pipenv install --dev` で構築してください。

```bash
pipenv run python main.py
pipenv run python scripts/check_source.py <site_id>
pipenv run python scripts/run.py sync-sources
pipenv run python -m unittest discover -s tests
```

`pipenv run python main.py` は実サイト、Firebase 認証情報、Firestore を使用するため、通常の検証では実行しないでください。CI は CI 設定に記載されたコマンドを使用します。

## 実装ルール

- Python 3.11 を基準とし、PEP 8、4スペースインデント、snake_case、型ヒントを使用する。
- import は標準ライブラリ、外部ライブラリ、ローカルモジュールの順に分ける。
- 新しい公開関数とクラスには、目的が分かる短い docstring を付ける。
- 広い `except Exception` は、サイト単位の障害分離や最上位ログなど必要な境界だけで使う。解析処理では想定例外を具体的に扱う。
- HTTP リクエストには必ず timeout と `raise_for_status()` を設定する。
- 相対 URL は `urllib.parse.urljoin` で解決する。
- 日時は保存形式との互換性を確認する。タイムゾーンを変更する場合は、既存 epoch への影響をテストで示す。
- `firebase_admin._apps` のようなライブラリ内部属性への新たな依存は増やさない。
- ライブラリ、API、フレームワーク、設定項目を変更・提案する場合は、可能な限り Context7 MCP で最新の公式ドキュメントを確認する。プロジェクト固有の挙動は実コードを優先する。

## データ契約

スクレイパーの返り値は、当面次のキーを持つ辞書のリストを維持します。

```python
{
    "url": str,
    "title": str,
    "epoch": int,
    "hash": str,
    "org": str,
}
```

`hash` は現在 `url`、`title`、`epoch` の SHA-256 です。生成規則の変更は重複登録につながるため、移行処理なしに変更しないでください。

サイト設定では少なくとも `name`、`url`、`useDefaultFunc`、`arg` が必要です。`useDefaultFunc` が `false` の場合は `funcID` も必要です。設定変更時は対象キーだけを編集し、`config/sources.json` 全体の並べ替えや整形を避けます。

## テスト方針

- 新しいテストは `tests/test_*.py` に置く。
- HTML/RSS の解析テストは `tests/fixtures/` の小さな固定ファイルを使い、実サイトにアクセスしない。
- Firestore は fake または mock に置き換え、実プロジェクトへ書き込まない。
- 各スクレイパーについて、正常系に加えて、セレクター不一致、欠損リンク、不正な日付のうち関係するケースを確認する。
- サイト定義を変更した場合は JSON の読込検証と、そのサイトだけを対象にした解析テストを行う。
- バグ修正では、可能な限り先に再現テストを追加する。

## セキュリティと運用上の注意

- `.env`、Firebase サービスアカウント JSON、トークン、秘密鍵を表示・編集・コミットしない。
- 現在ルートにある `ws-db-11235813-firebase-adminsdk-lh4mi-50c38e64b5.json` は秘密情報として扱う。内容を回答、ログ、テスト fixture、差分へ転載しない。
- 認証情報は `FIREBASE_ADMIN_SDK` 環境変数でリポジトリ外のパスを指定できる。資格情報の削除やローテーションは、所有者の確認を得て別作業として行う。
- Firestore への追加、GitHub Actions の実行、実サイトへの大量アクセスは副作用のある操作である。明示的な依頼なしに実行しない。
- ログに記事本文や認証情報を残さない。URL を記録する場合もクエリに秘密情報がないことを確認する。

## 変更時の進め方

1. `rg` で対象シンボル、設定キー、呼び出し元を確認する。
2. 関係する実ファイルと既存差分を読み、ユーザーの変更を上書きしない。
3. 変更範囲を一つの責務に絞る。構成移動時は import、設定パス、README、CI を忘れず確認する。
4. ネットワークや実DBを使わない最小の検証を実行する。
5. 最終報告には変更ファイル、検証コマンド、未検証事項、運用への影響を記載する。

不明点があっても、実コード、設定、呼び出し元から安全に判断できる範囲は先に調査します。データ削除、資格情報、外部サービスへの書込み、互換性を壊す選択が必要な場合は、実行前に確認してください。
