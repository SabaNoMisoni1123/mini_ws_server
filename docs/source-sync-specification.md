# 情報源設定と Firestore の同期仕様

## 目的

`config/sources.json` を情報源一覧の唯一の正とし、Firestore の `siteData`
コレクションと同期する運用コマンドを追加する。

設定から削除された情報源は、同じ ID の記事コレクションをローカルにバックアップしてから
Firestore 上の記事と `siteData` 文書を削除する。`config/disabled_sources.json` は本機能の
対象外とする。

この文書でいう設定ファイルは `config/sources.json` である。`config/source.json` という
単数形のファイルは使用しない。

## 対象データ

- 正とする入力: `config/sources.json`
- 同期先: Firestore の `siteData` コレクション
- 情報源の識別子: `sources.json` の最上位キーおよび `siteData.id`
- 同期する `siteData` の属性: `id`、`name`、`url`、`no`
- 削除時にバックアップ・削除する記事: Firestore のコレクション名が情報源 ID と一致する全記事

`useDefaultFunc`、`funcID`、`arg` はスクレイピング設定であり、`siteData` へは保存も比較も
しない。`timeLog`、および設定に残っている情報源の記事コレクションも変更しない。

## コマンドライン仕様

既存の統一入口 `scripts/run.py` に `sync-sources` サブコマンドを追加する。

```console
# 差分確認のみ（Firestore は変更しない）
python scripts/run.py sync-sources

# 追加・更新・再採番のみを反映する場合
python scripts/run.py sync-sources --apply

# 削除を含めて反映する場合
python scripts/run.py sync-sources --apply --confirm-delete

# 削除時のバックアップ先を明示する場合
python scripts/run.py sync-sources --apply --confirm-delete --backup-dir /path/to/backup
```

引数は以下のとおりとする。

| 引数 | 既定値 | 仕様 |
| --- | --- | --- |
| `--apply` | なし | 指定時だけ Firestore を変更する。指定しない場合は dry-run。 |
| `--confirm-delete` | なし | 削除対象がある `--apply` 実行で必須。削除対象がない場合は不要。 |
| `--backup-dir DIR` | カレントディレクトリの `backup-YYYY-MM-DD` | 削除対象の記事バックアップを置くディレクトリ。指定時は `DIR` をそのまま使用する。 |
| `--overwrite-backup` | `false` | 既存のバックアップファイルを上書きしてよいことを明示する。 |

`YYYY-MM-DD` はコマンドを開始したローカル日時の日付である。既定のバックアップ先が存在しない
場合は作成する。`--backup-dir` で指定したディレクトリも、存在しなければ作成する。

削除対象がない場合、`--backup-dir` は不要であり、既定バックアップディレクトリも作成しない。
dry-run はバックアップディレクトリを作成しない。

## `no` の規則

`no` は一覧の整列順を表す重みであり、`sources.json` のトップレベルの記載順で決める。

- 先頭の情報源を `0` とする。
- 以降は 1 ずつ増加させる。
- 同期のたびに、設定に存在するすべての情報源の期待値を計算する。
- 既存の `no` が期待値と異なる場合は、`name` と `url` が同一でも更新対象とする。

JSON のキー順序は設定上の意味を持つため、`sources.json` を不要に並べ替えない。

## 差分判定

Firestore の `siteData` は必要な属性をすべて読み取り、文書参照とともに ID 単位で扱う。

| 条件 | 判定 | `--apply` 時の処理 |
| --- | --- | --- |
| 設定にのみある ID | 追加 | `id`、`name`、`url`、期待 `no` の文書を追加する。 |
| 両方にあり、`name`、`url`、`no` のいずれかが異なる | 更新 | 当該3属性を設定値・期待値で更新する。`id` は変更しない。 |
| 両方にあり、すべて一致 | 変更なし | 何もしない。 |
| Firestore にのみある ID | 削除 | バックアップ検証後、記事コレクション、続いて `siteData` 文書を削除する。 |

`siteData` に同じ `id` を持つ文書が複数ある、または `id` がない・空の文書がある場合は、
データ不整合とみなす。この場合は差分を表示して異常終了し、Firestore とローカルファイルを
一切変更しない。

## 削除とバックアップの仕様

削除対象 ID ごとに、バックアップディレクトリ直下へ次のファイルを出力する。

```text
backup-YYYY-MM-DD/
├── <site_id>.json
└── manifest.json
```

`<site_id>.json` は既存の `ArticleDataTransfer.write_articles()` と同じ、記事オブジェクトの
JSON 配列とする。各記事は `url`、`title`、`epoch`、`hash`、`org` を持たなければならない。

`manifest.json` には少なくとも、実行日時、設定ファイルのパス、dry-run/適用の別、バックアップ
対象 ID、各 ID の記事件数、出力ファイル名、最終結果を保存する。認証情報や記事本文は保存しない。

同名の `<site_id>.json` または `manifest.json` がすでに存在する場合、既定では処理を失敗させる。
`--overwrite-backup` 指定時だけ上書きを許可する。

記事を削除できるのは、次のすべてを満たした場合だけとする。

1. 対象 ID の全記事を取得できた。
2. JSON の書込みが成功した。
3. 書き込んだ JSON を `read_articles()` で読み直せた。
4. 読み直した記事数と、記事の `hash` の集合が取得時と一致した。

記事に必須フィールドの欠損などがありバックアップ検証に失敗した場合、その ID の記事および
`siteData` は削除しない。

## 反映手順と失敗時の扱い

1. `sources.json` を読み、各情報源に期待する `no` を割り当てる。
2. `siteData` を全件読み、ID の重複・欠損を検証する。
3. 追加・更新・削除・変更なしの差分計画を作成し、標準出力に表示する。
4. dry-run なら終了する。
5. 削除対象があれば `--confirm-delete` の有無を検証する。
6. 削除対象の全記事をバックアップし、全件でバックアップ検証を完了する。この段階で失敗した場合、Firestore を変更せず終了する。
7. 追加・更新を実行する。ここには全情報源の `no` 再採番を含む。
8. 削除対象ごとに記事コレクションを削除する。
9. 記事コレクションの削除が成功した ID の `siteData` 文書を削除する。
10. `manifest.json` と標準出力に ID ごとの結果・集計を記録する。

Firestore には記事コレクション削除と `siteData` 文書削除をまたぐ原子的トランザクションはない。
記事削除に失敗した場合は対応する `siteData` 文書を削除しない。削除途中の状態になった場合でも
検証済みバックアップは残るため、利用者はバックアップを使って復旧できる。

追加・更新・削除の個別操作で失敗した ID は記録し、他の独立した ID の処理は継続する。コマンドは
失敗した ID が1件でもあれば非ゼロで終了する。

## 出力

dry-run と適用時の両方で、ID 別の処理内容と以下の合計を出力する。

- 追加数
- 更新数（`no` のみの更新を含む）
- 変更なし数
- 削除予定数または削除完了数
- バックアップ済み記事数
- 失敗数と失敗した ID

削除を伴う適用では、バックアップディレクトリへのパスも最後に表示する。

## 実装配置

責務を分離するため、実装は次の配置を想定する。

- `src/mini_ws_server/source_sync.py`: 差分計画、バックアップ検証、同期ユースケース
- `src/mini_ws_server/repositories/firestore.py`: `siteData` の全件取得・追加・更新・文書削除に必要なリポジトリ操作
- `scripts/run.py`: `sync-sources` の引数定義と実行入口
- `tests/test_source_sync.py`: fake リポジトリによるユースケースのテスト
- `tests/test_firestore_repository.py`（必要なら）: リポジトリの呼出し内容を mock で検証するテスト
- `README.md`: 新コマンド、削除時のバックアップ、確認オプションの説明

Firestore へのアクセスはリポジトリに閉じ込める。スクレイパーおよび実サイトへの HTTP アクセスは
本機能に含めない。

## 必須テスト

- 設定にのみある ID の追加
- `name`、`url`、`no` の各更新、および `no` の全件再採番
- 設定にない ID の記事バックアップ、記事コレクション削除、`siteData` 削除
- 空の記事コレクションを持つ ID のバックアップと削除
- 必須フィールド欠損など、バックアップ検証失敗時に Firestore を一切変更しないこと
- 記事削除失敗時に、対応する `siteData` を削除しないこと
- `siteData.id` の重複・欠損時に変更を行わないこと
- dry-run が Firestore とバックアップディレクトリを変更しないこと
- 既存バックアップを既定で上書きせず、`--overwrite-backup` 時だけ上書きすること
- 削除対象がある適用で `--confirm-delete` がない場合に失敗すること
