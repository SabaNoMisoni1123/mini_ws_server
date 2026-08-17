# `scripts/run.py update` を GitHub Actions で実行するための設定手順

更新日: 2026-08-17

## 1. 目的と実行時の既定動作

この文書では、GitHub Actions から次のコマンドを追加オプションなしで実行するために必要な設定を整理する。

```bash
python scripts/run.py update
```

このコマンドの既定動作は次のとおり。

- `config/sources.json` にあるすべての情報元を対象にする。
- 実行日を含む過去3日分を確認する。
- 各情報元の直近50件の `hash` と照合し、未登録の記事を Firestore に追加する。
- 最後に `timeLog/lastTime` の `lastTimeEpoch` を更新する。
- 進行状況とエラーは標準エラー、構造化した最終結果 JSON は標準出力へ出力する。
- 情報元単位・記事単位の失敗は他の処理を止めず、すべて処理した後に終了コード `1` を返す。
- ログファイルは既定では作らず、必要な場合だけ `--log-file PATH` を指定する。

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

このドキュメントがなくても記事更新処理自体は継続するが、最終実行時刻の更新失敗が
標準エラーと結果 JSON に記録され、コマンドは終了コード `1` を返す。

### 3.3 サービスアカウントを準備する

GitHub Actions 専用のサービスアカウントを用意し、対象 Firestore に対して次の操作だけを実行できる権限を付与する。

- 情報元 ID と同名の各記事コレクションの読み取りと追加
- `timeLog/lastTime` の更新

権限は対象プロジェクトの運用方針に従い、必要最小限にする。既存のローカル用秘密鍵を転用するより、用途を GitHub Actions に限定した認証情報を分ける。

Firebase Admin Python SDK の `credentials.Certificate()` は、サービスアカウント JSON のファイルパスを受け取り、その認証情報で Firebase アプリを初期化する。本プロジェクトもこの方式を使用している。

## 4. GitHub Actions Secret の登録

`docs/github_actions_firebase_webscraping_guide.md` に合わせ、Secret 名は次で統一する。

```text
FIREBASE_SERVICE_ACCOUNT
```

GitHub の対象リポジトリで、`Settings` → `Secrets and variables` → `Actions` → `New repository secret` を開き、サービスアカウント JSON の内容全体を登録する。JSON をリポジトリ内のファイルとして追加してはいけない。

GitHub CLI を使用する場合は、認証 JSON の内容を画面へ出力せず、ファイルから直接登録する。

```bash
gh secret set FIREBASE_SERVICE_ACCOUNT < /path/to/firebase-service-account.json
gh secret list
```

`gh secret list` では Secret 名が存在することだけを確認する。値は取得・表示しない。

## 5. 更新用 Workflow

既存の `.github/workflows/main.yml` は push / pull request 時のテスト専用である。更新処理は副作用と認証情報を持つため、別ファイル `.github/workflows/update.yml` として分離する。

更新専用の `.github/workflows/update.yml` は、手動実行と日本時間での定期実行を分離せず、
同じ更新処理として定義している。手動実行時だけ `days_range` を指定でき、定期実行では
既定値の3日を使用する。

```yaml
name: Update Firestore

on:
  workflow_dispatch:
    inputs:
      days_range:
        description: "取得対象とする過去の日数"
        required: true
        default: 3
        type: number
  schedule:
    - cron: "15 12,15,18 * * *"
      timezone: "Asia/Tokyo"

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

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Prepare Firebase credentials
        env:
          FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
        run: |
          test -n "$FIREBASE_SERVICE_ACCOUNT"
          printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "$RUNNER_TEMP/firebase-service-account.json"
          chmod 600 "$RUNNER_TEMP/firebase-service-account.json"

      - name: Run update
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ runner.temp }}/firebase-service-account.json
          DAYS_RANGE: ${{ inputs.days_range || 3 }}
        run: python scripts/run.py update --days-range "$DAYS_RANGE"
```

設定上の要点は次のとおり。

- Secret の JSON は実行時だけ `$RUNNER_TEMP` 配下へ作成する。
- `GOOGLE_APPLICATION_CREDENTIALS` には一時ファイルの絶対パスを渡す。
- `permissions` はリポジトリ内容の読み取りだけに限定する。
- `concurrency` により、定期実行と手動実行が重なって同時更新されることを防ぐ。
- 手動実行では `days_range`、定期実行では3日を更新対象期間として渡す。
- 標準出力と標準エラーは Workflow Run のログへ保存されるため、通常のログ Artifact は作らない。
- 一件でも更新に失敗すると更新ステップが非ゼロで終了し、Workflow も失敗表示になる。
- 実行後の一時ファイルは GitHub-hosted runner の破棄とともに削除される。

## 6. 初回の手動確認

`workflow_dispatch` は Workflow ファイルが既定ブランチに存在するときに利用できる。

GitHub の画面から実行する場合:

1. Workflow ファイルを既定ブランチへ反映する。
2. 対象リポジトリの `Actions` → `Update Firestore` を開く。
3. `Run workflow` を選び、実行するブランチと `days_range`（通常は `3`）を確認して、
   もう一度 `Run workflow` を押す。

GitHub CLI から実行する場合:

```bash
gh workflow run update.yml --ref main -f days_range=3
gh run watch
```

既定ブランチ名が `main` でない場合は `--ref` をそのブランチ名へ変更する。実行状況を
一覧で確認するだけなら `gh run list --workflow update.yml`、特定の実行ログを表示するなら
`gh run view <run-id> --log` を使用する。

実行後は次を確認する。

1. `Prepare Firebase credentials` が成功することを確認する。
2. `Run update` の最後に、全体状態、情報元 ID ごとの追加件数、エラー配列を持つ JSON が
   出力されることを確認する。更新開始前の致命的失敗では `status` が `failed` になる。
3. Firestore で想定した記事コレクションだけに追加されていることを確認する。
4. `timeLog/lastTime.lastTimeEpoch` が更新されていることを確認する。
5. Workflow Run のログと結果 JSON に認証エラーや部分失敗がないことを確認する。

## 7. 定期実行の設定

初期設定では、日本時間の毎日 12:15、15:15、18:15 に実行する。同じ分で複数の時刻を指定する場合は、cron の「時」フィールドをカンマ区切りにできる。

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "15 12,15,18 * * *"
      timezone: "Asia/Tokyo"
```

曜日や分が異なるなど、実行条件が別の場合は `schedule` の項目を複数記述する。

```yaml
schedule:
  - cron: "15 12 * * 1-5"
    timezone: "Asia/Tokyo"
  - cron: "45 18 * * 6,0"
    timezone: "Asia/Tokyo"
```

GitHub のスケジュール実行は指定時刻ちょうどに開始されない場合がある。更新間隔に厳密な時刻保証が必要な用途には使用しない。

## 8. 設定完了チェックリスト

- [ ] 対象 Firebase プロジェクトと `project_id` が一致している。
- [ ] Cloud Firestore の既定データベースが存在する。
- [ ] `timeLog/lastTime` ドキュメントが存在する。
- [ ] GitHub Actions 専用サービスアカウントに必要最小限の権限がある。
- [ ] Repository Secret `FIREBASE_SERVICE_ACCOUNT` が登録されている。
- [ ] 認証 JSON が Git 管理対象に追加されていない。
- [ ] `.github/workflows/update.yml` が手動実行できる。
- [ ] 既定の3日範囲で記事が重複せず追加される。
- [ ] 出力 JSON の `status` が `completed` で、`errors` が空である。
- [ ] 手動確認後にだけ `schedule` を有効化している。

## 9. トラブルシューティング

### Secret が未設定または空

`Prepare Firebase credentials` の `test -n` で停止する。Secret 名が `FIREBASE_SERVICE_ACCOUNT` と完全一致しているか確認する。fork からの pull request など、Secrets が渡されないイベントでは更新処理を実行しない。

### 認証 JSON を読み込めない

`credentials.Certificate()` のエラーになる。Secret に JSON 全体が登録されているか、対象プロジェクトの有効なサービスアカウント鍵かを確認する。秘密鍵の内容を Actions ログへ出力してはいけない。

### Firestore で権限エラーになる

サービスアカウントが対象プロジェクトに属しているか、記事コレクションの読み取り・追加と `timeLog/lastTime` の更新に必要な IAM 権限があるか確認する。

### 特定の情報元だけ失敗する

Workflow Run のログと結果 JSON で該当する `source_id` を確認する。外部サイトの構造変更、
HTTP エラー、日付解析失敗などは情報元単位で記録される。

### 部分失敗を成功扱いにしたい

既定では部分失敗時に終了コード `1` を返す。互換目的の best-effort 運用に限り
`--allow-partial-success` を指定すると、結果 JSON にエラーを残したまま終了コード `0` にできる。

## 10. 参照先

- リポジトリ内の実行入口: `scripts/run.py`
- 更新処理: `src/mini_ws_server/cli.py`
- Firestore 認証処理: `src/mini_ws_server/repositories/firestore.py`
- 情報元設定: `config/sources.json`
- 既存テスト Workflow: `.github/workflows/main.yml`
- GitHub Actions Secrets: <https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets>
- Firebase Admin Python SDK credentials: <https://github.com/firebase/firebase-admin-python/blob/main/_autodocs/api-reference/credentials.md>
