# `scripts/run.py update` を GitHub Actions で実行するための設定手順

更新日: 2026-08-17

## 1. 目的と実行時の既定動作

この文書では、GitHub Actions から次のコマンドを追加オプションなしで実行するために必要な設定を整理する。

```bash
pipenv run python scripts/run.py update
```

このコマンドの既定動作は次のとおり。

- `config/sources.json` にあるすべての情報元を対象にする。
- 実行日を含む過去3日分を確認する。
- 各情報元の直近50件の `hash` と照合し、未登録の記事を Firestore に追加する。
- 最後に `timeLog/lastTime` の `lastTimeEpoch` を更新する。
- 標準エラー出力と、リポジトリルートの `scraper.log` にログを出力する。
- 情報元単位の失敗は他の情報元の処理を止めず、結果の件数を `-1` として処理を継続する。

`update` は外部サイトへアクセスし、Firestore を変更する。本番用の認証情報を設定する前に、対象が意図した Firebase プロジェクトであることを確認する。

## 2. 全体の設定順序

次の順序で設定する。

1. Firebase / Firestore を準備する。
2. 専用サービスアカウントと権限を準備する。
3. サービスアカウント JSON を GitHub Actions Secret に登録する。
4. 更新専用の GitHub Actions Workflow を追加する。
5. 手動実行で認証・取得・保存を確認する。
6. 問題がなければ定期実行を有効にする。

## 3. Firebase / Firestore 側の準備

### 3.1 対象プロジェクトを確定する

Firebase Console または Google Cloud Console で、記事を書き込む対象プロジェクトを確定する。サービスアカウント JSON の `project_id` がこのプロジェクトと一致する必要がある。

### 3.2 Firestore データベースを準備する

対象プロジェクトで Cloud Firestore を有効にし、既定データベースを作成する。このプロジェクトは `firestore.client()` で既定データベースへ接続する。

記事用コレクションは情報元 ID ごとに書き込み時に作成される。一方、最終実行時刻は次の既存ドキュメントに対して `update()` されるため、先に用意しておく。

```text
timeLog/lastTime
└── lastTimeEpoch: 0
```

このドキュメントがなくても記事更新処理自体は継続するが、最終実行時刻の更新失敗が `scraper.log` に記録される。

### 3.3 サービスアカウントを準備する

GitHub Actions 専用のサービスアカウントを用意し、対象 Firestore に対して次の操作だけを実行できる権限を付与する。

- 情報元 ID と同名の各記事コレクションの読み取りと追加
- `timeLog/lastTime` の更新

権限は対象プロジェクトの運用方針に従い、必要最小限にする。既存のローカル用秘密鍵を転用するより、用途を GitHub Actions に限定した認証情報を分ける。

Firebase Admin Python SDK の `credentials.Certificate()` は、サービスアカウント JSON のファイルパスを受け取り、その認証情報で Firebase アプリを初期化する。本プロジェクトもこの方式を使用している。

## 4. GitHub Actions Secret の登録

Secret 名は次で統一する。

```text
FIREBASE_ADMIN_SDK_JSON
```

GitHub の対象リポジトリで、`Settings` → `Secrets and variables` → `Actions` → `New repository secret` を開き、サービスアカウント JSON の内容全体を登録する。JSON をリポジトリ内のファイルとして追加してはいけない。

GitHub CLI を使用する場合は、認証 JSON の内容を画面へ出力せず、ファイルから直接登録する。

```bash
gh secret set FIREBASE_ADMIN_SDK_JSON < /path/to/firebase-service-account.json
gh secret list
```

`gh secret list` では Secret 名が存在することだけを確認する。値は取得・表示しない。

## 5. 更新用 Workflow の追加

既存の `.github/workflows/main.yml` は push / pull request 時のテスト専用である。更新処理は副作用と認証情報を持つため、別ファイル `.github/workflows/update.yml` として分離する。

まずは手動実行だけを有効にして、次の内容で作成する。

```yaml
name: Update Firestore

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: firestore-update
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install Pipenv and dependencies
        run: |
          python -m pip install --upgrade pip pipenv
          pipenv install --dev

      - name: Prepare Firebase credentials
        env:
          FIREBASE_ADMIN_SDK_JSON: ${{ secrets.FIREBASE_ADMIN_SDK_JSON }}
        run: |
          test -n "$FIREBASE_ADMIN_SDK_JSON"
          printf '%s' "$FIREBASE_ADMIN_SDK_JSON" > "$RUNNER_TEMP/firebase-service-account.json"
          chmod 600 "$RUNNER_TEMP/firebase-service-account.json"

      - name: Run update with defaults
        env:
          FIREBASE_ADMIN_SDK: ${{ runner.temp }}/firebase-service-account.json
        run: pipenv run python scripts/run.py update

      - name: Upload scraper log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scraper-log-${{ github.run_id }}
          path: scraper.log
          if-no-files-found: ignore
          retention-days: 7
```

設定上の要点は次のとおり。

- Secret の JSON は実行時だけ `$RUNNER_TEMP` 配下へ作成する。
- `FIREBASE_ADMIN_SDK` には一時ファイルの絶対パスを渡す。
- `permissions` はリポジトリ内容の読み取りだけに限定する。
- `concurrency` により、定期実行と手動実行が重なって同時更新されることを防ぐ。
- 実行後の一時ファイルは GitHub-hosted runner の破棄とともに削除される。

## 6. 初回の手動確認

1. Workflow ファイルを既定ブランチへ反映する。
2. GitHub の `Actions` → `Update Firestore` → `Run workflow` から実行する。
3. `Prepare Firebase credentials` が成功することを確認する。
4. `Run update with defaults` の最後に、情報元 ID ごとの追加件数を持つ JSON が出力されることを確認する。
5. Firestore で想定した記事コレクションだけに追加されていることを確認する。
6. `timeLog/lastTime.lastTimeEpoch` が更新されていることを確認する。
7. Artifact の `scraper.log` に認証エラーや情報元単位の失敗がないことを確認する。

注意: 現在の実装では、一部の情報元が失敗して結果が `-1` になっても、コマンド全体は終了コード `0` になる。Workflow が成功表示でも、初回確認では出力 JSON と `scraper.log` の両方を確認する。

## 7. 定期実行の有効化

手動実行が安定してから `schedule` を追加する。GitHub Actions の cron は UTC で指定する。例として、日本時間の毎日 06:15 に実行する場合は前日の 21:15 UTC となる。

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "15 21 * * *"
```

GitHub のスケジュール実行は指定時刻ちょうどに開始されない場合がある。更新間隔に厳密な時刻保証が必要な用途には使用しない。

## 8. 設定完了チェックリスト

- [ ] 対象 Firebase プロジェクトと `project_id` が一致している。
- [ ] Cloud Firestore の既定データベースが存在する。
- [ ] `timeLog/lastTime` ドキュメントが存在する。
- [ ] GitHub Actions 専用サービスアカウントに必要最小限の権限がある。
- [ ] Repository Secret `FIREBASE_ADMIN_SDK_JSON` が登録されている。
- [ ] 認証 JSON が Git 管理対象に追加されていない。
- [ ] `.github/workflows/update.yml` が手動実行できる。
- [ ] 既定の3日範囲で記事が重複せず追加される。
- [ ] 出力 JSON に `-1` がなく、`scraper.log` にエラーがない。
- [ ] 手動確認後にだけ `schedule` を有効化している。

## 9. トラブルシューティング

### Secret が未設定または空

`Prepare Firebase credentials` の `test -n` で停止する。Secret 名が `FIREBASE_ADMIN_SDK_JSON` と完全一致しているか確認する。fork からの pull request など、Secrets が渡されないイベントでは更新処理を実行しない。

### 認証 JSON を読み込めない

`credentials.Certificate()` のエラーになる。Secret に JSON 全体が登録されているか、対象プロジェクトの有効なサービスアカウント鍵かを確認する。秘密鍵の内容を Actions ログへ出力してはいけない。

### Firestore で権限エラーになる

サービスアカウントが対象プロジェクトに属しているか、記事コレクションの読み取り・追加と `timeLog/lastTime` の更新に必要な IAM 権限があるか確認する。

### 特定の情報元だけ `-1` になる

Artifact の `scraper.log` で該当する `Failed site: <site_id>` を確認する。外部サイトの構造変更、HTTP エラー、日付解析失敗などは情報元単位で記録される。

### 実行全体を失敗扱いにしたい

現状は情報元単位の失敗があっても終了コード `0` になる。Actions の成否を厳密にしたい場合は、別変更として `scraper.errors` が存在するときに非ゼロ終了する運用モードまたは検証処理を追加する。

## 10. 参照先

- リポジトリ内の実行入口: `scripts/run.py`
- 更新処理: `src/mini_ws_server/cli.py`
- Firestore 認証処理: `src/mini_ws_server/repositories/firestore.py`
- 情報元設定: `config/sources.json`
- 既存テスト Workflow: `.github/workflows/main.yml`
- GitHub Actions Secrets: <https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets>
- Firebase Admin Python SDK credentials: <https://github.com/firebase/firebase-admin-python/blob/main/_autodocs/api-reference/credentials.md>
