# GitHub Actions を既定実行環境とする更新コマンド改修案

更新日: 2026-08-18

## 1. 結論

GitHub Actions は `run` ステップでプロセスが出力した標準出力と標準エラーを、Workflow
Run のログとして自動的に保存・表示する。そのため、Actions でログを確認するだけなら、
Python が別途 `scraper.log` を生成し、Artifact としてアップロードする必要はない。

更新コマンドの既定動作は、GitHub Actions に限らず cron やコンテナでも扱いやすい次の形に
する。

- 進行状況とエラーは標準エラーへ出力する。
- 機械可読な最終結果だけを標準出力へ JSON で出力する。
- ログファイルは既定では作らない。必要な場合だけ `--log-file` で有効にする。
- 一部でも更新に失敗したら、全情報元の処理を続けた後に非ゼロで終了する。
- 従来どおり部分失敗を成功扱いにする場合だけ、明示的なフラグを指定する。
- `GITHUB_ACTIONS` の有無で Python 側の動作を暗黙に切り替えない。

この方針では、デフォルトが自動実行向けの厳格な動作となり、ローカル固有・互換目的の動作を
フラグへ隔離できる。

## 2. GitHub Actions のログと Artifact

### 2.1 Actions が標準で扱うログ

各ステップの標準出力と標準エラーは、そのステップの実行ログとして Actions 画面から確認
できる。GitHub CLI では次のように取得できる。

```bash
gh run view <run-id> --log
```

したがって、通常の診断ログは Python の `logging.StreamHandler` だけで十分である。
Python の `logging.StreamHandler()` は既定で標準エラーへ出力するため、最終結果を出す標準出力
と分離できる。

### 2.2 Artifact が適するもの

Artifact は、ログ表示の代替というより、実行によって生成されたファイルを後から取得する
ための仕組みである。たとえば、解析結果一式、デバッグ用 HTML、レポート、バックアップなどが
該当する。

`scraper.log` を長期保管したい、または一括ダウンロードしたいという明示的な要件がある場合は
Artifact に残してよい。ただし現在の Workflow のように常にアップロードする必要はなく、
`--log-file` を指定した実行だけを対象にする方が責務が明確になる。

```bash
gh run download <run-id>
```

## 3. 現状と問題点

### 3.1 ログファイルが常に作られる

`src/mini_ws_server/cli.py` の `main()` は、次の二つの Handler を常に設定している。

- `StreamHandler`: Actions の実行ログへ流れるため必要。
- `FileHandler(Path.cwd() / "scraper.log")`: Actions の通常ログには不要。

このため、書き込み可能なカレントディレクトリを暗黙に要求し、ライブラリとして `main()` を
呼び出した場合にもファイルを作る。ログ設定が既に済んでいるプロセスでは
`logging.basicConfig()` が期待どおり反映されない可能性もある。

### 3.2 部分失敗でも終了コードが `0` になる

`MinistrySiteDataGetter.update_all_data()` は情報元単位の例外を捕捉し、処理を継続する。
これは障害分離として妥当だが、`cli.main()` は `scraper.errors` が存在しても最後に `0` を返す。
その結果、Actions では更新漏れがあっても Workflow が成功表示になる。

「途中で止めないこと」と「最終的に成功扱いすること」は分けるべきである。全情報元を処理して
結果を集約した後、部分失敗があれば既定では終了コード `1` にする。

### 3.3 すべての保存失敗が集約されていない

現状では次の失敗がログに記録されても、`scraper.errors` に必ずしも反映されない。

- 記事1件の `add_article()` 失敗
- `timeLog/lastTime` の更新失敗
- `load_current_hashes()` の失敗

特に `load_current_hashes()` は例外時に空集合を返すため、重複判定ができないまま追加処理を
続ける可能性がある。Actions 対応以前に、更新結果を正しく判定するための改善対象である。

### 3.4 結果 JSON が成功・失敗の詳細を十分に表さない

現在の標準出力は情報元 ID と追加件数の辞書で、`-1` が部分失敗を表す。人間には確認できるが、
失敗理由や全体状態を機械的に扱いにくい。

## 4. 提案する CLI 仕様

### 4.1 デフォルト実行

```bash
python scripts/run.py update
```

既定動作を次のようにする。

| 項目 | 既定動作 |
| --- | --- |
| 進行・警告・例外ログ | 標準エラーへ出力 |
| 最終結果 | 標準出力へ JSON を1件出力 |
| ログファイル | 作成しない |
| 情報元単位の失敗 | 他の情報元は継続する |
| 最終終了コード | 全成功は `0`、一件以上の失敗は `1` |
| ログレベル | `INFO` |

### 4.2 追加するフラグ

```text
--log-file PATH
    指定された場合だけ PATH へログを複製する。

--log-level {DEBUG,INFO,WARNING,ERROR}
    ログレベルを変更する。既定値は INFO。

--allow-partial-success
    情報元単位・記事単位などの部分失敗があっても終了コードを 0 にする。
    従来動作が必要な運用だけで使用する。
```

`--github-actions` や `--local` は追加しない。標準ストリームと終了コードを正しく使えば、実行
環境ごとの分岐は不要であり、ローカルでも同じ挙動を再現できるためである。

ローカルで従来と同様にファイルを残し、部分失敗を成功扱いにする場合は明示する。

```bash
pipenv run python scripts/run.py update \
  --log-file scraper.log \
  --allow-partial-success
```

## 5. 提案する結果形式

既存の情報元別件数を残しつつ、全体状態と失敗内容を追加した結果オブジェクトを導入する。

```json
{
  "status": "completed_with_errors",
  "added": {
    "exampleSource": 3,
    "failedSource": 0
  },
  "errors": [
    {
      "scope": "source",
      "source_id": "failedSource",
      "message": "HTTP request failed"
    }
  ]
}
```

認証情報、レスポンス本文、記事本文は結果やログへ含めない。例外文字列に URL を含める場合も、
秘密のクエリパラメータがないことを確認する。

互換性を重視する場合は、第1段階では既存 JSON を維持し、終了コードとログ出力だけを変更する。
構造化結果への変更は、出力を利用する外部処理の有無を確認してから第2段階で行う。

## 6. コード構成の改修案

### 6.1 `src/mini_ws_server/cli.py`

- `configure_logging(log_level, log_file=None)` を追加する。
- 既定 Handler は `StreamHandler` のみにする。
- `log_file` が指定された場合だけ `FileHandler` を追加する。
- `main()` に `log_file`、`log_level`、`allow_partial_success` を渡せるようにする。
- 集約結果にエラーがあれば、結果 JSON を出した後に既定で `1` を返す。
- `command_line_main()` にも同じ引数を追加し、パッケージの実行入口との差をなくす。

アプリケーション内部で root logger を無条件に上書きしないよう、Handler の設定場所は CLI の
入口だけに限定する。スクレイパーや repository は引き続きモジュール Logger を使用する。

### 6.2 `scripts/run.py`

- `update` サブコマンドへ三つのフラグを追加する。
- 既定値かどうかで `cli.main()` の呼び方を分岐している現状をやめ、すべての値を明示して渡す。
- ヘルプと `RUN_ARGUMENT_GUIDE` を同時に更新する。

### 6.3 `src/mini_ws_server/service.py`

- 情報元単位の例外だけでなく、記事追加失敗と最終時刻更新失敗も結果へ集約する。
- 1件の失敗で全情報元を中断せず、可能な処理は最後まで継続する。
- 重複確認を読み込めなかった情報元は、安全のため記事追加を行わず失敗として記録する。
- 可能であれば `UpdateResult`、`UpdateError` の dataclass を `models.py` に定義する。

`FirestoreRepository.load_current_hashes()` が空集合を返して障害を隠す設計は変更し、例外を
service 境界まで伝播させる。サイト単位の障害分離は service 側で行う。

### 6.4 `.github/workflows/update.yml`

Python の既定動作が標準ストリームだけになった後は、通常運用から次を削除する。

```yaml
- name: Upload scraper log
  if: always()
  uses: actions/upload-artifact@v4
  with:
    path: scraper.log
```

更新ステップが非ゼロ終了すれば、そのまま Workflow が失敗表示になる。追加の Actions 固有判定は
不要である。失敗時のログは Actions 画面または `gh run view <run-id> --log` で確認する。

一時的にファイルログも必要なデバッグ Workflow では、コマンドに
`--log-file "$RUNNER_TEMP/scraper.log"` を追加し、そのファイルだけを `if: always()` で Artifact
へアップロードする。

## 7. テスト方針

外部サイトや Firestore を使用せず、次を追加する。

1. デフォルト実行では `scraper.log` が作られない。
2. `--log-file` 指定時だけファイルが作られる。
3. ログは標準エラー、結果 JSON は標準出力へ分離される。
4. 全成功時の終了コードは `0` になる。
5. 情報元単位の失敗後も残りを処理し、最終終了コードは `1` になる。
6. `--allow-partial-success` 指定時だけ、同じ部分失敗で終了コードが `0` になる。
7. 記事追加失敗と最終時刻更新失敗が集約結果へ含まれる。
8. 保存済みハッシュ取得失敗時には、その情報元へ記事を追加しない。
9. `--log-level` の不正値を `argparse` が拒否する。
10. 結果やログに認証情報が出力されない。

CLI テストでは `redirect_stdout`、`redirect_stderr`、一時ディレクトリ、fake repository を使う。
ログ Handler はテスト間で残らないように明示的に解除する。

## 8. 実装順序

1. 失敗を再現する service / CLI テストを追加する。
2. 更新結果とエラーの集約方法を導入する。
3. デフォルトの終了コードを厳格化し、互換フラグを追加する。
4. ログ設定を CLI 入口へ分離し、ファイル出力をオプトインにする。
5. `scripts/run.py`、公開コマンド、README の引数説明を揃える。
6. Workflow から通常時の Artifact アップロードを削除する。
7. fake を使った全テストと Workflow 構文検証を行う。
8. 手動 Workflow を一度実行し、部分失敗時にジョブが失敗表示になることを確認する。

手順8だけは実サイトへのアクセスと Firestore 書き込みを伴うため、認証先と実行対象を確認して
明示的に実施する。

## 9. 互換性と移行上の注意

- 部分失敗時の終了コードが `0` から `1` へ変わる。既存の cron や監視が終了コードを利用して
  いる場合は期待どおりか確認する。
- `scraper.log` に依存するローカル運用には `--log-file scraper.log` を追加する。
- `main.py` や `mini-ws-update` からも同じフラグを指定できるよう、互換入口を確認する。
- 結果 JSON の構造変更は外部利用者へ影響するため、終了コード・ログの改修と分離してもよい。
- `--allow-partial-success` は移行用または明確な best-effort 運用向けとし、Actions の定期更新では
  使用しない。

## 10. 公式ドキュメント

- [Workflow Run の履歴とログの表示](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history)
- [Workflow Artifact のダウンロード](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
- [Workflow command と job summary](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
