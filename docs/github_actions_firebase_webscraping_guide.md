# PythonウェブスクレイパーをGitHub Actionsで定期実行しFirebaseへ保存する手順書

更新日: 2026-08-12

## 1. 結論

今回の構成では、以下の方式を推奨する。

1. 既存のPythonスクレイピングプログラムは原則変更しない
2. Firebaseへの保存には **Firebase Admin SDK** を使用する
3. GitHub ActionsからFirebaseへ接続するための認証情報は、ソースコードや設定ファイルへハードコードしない
4. 初期構築では **Firebase / Google CloudのサービスアカウントJSONをGitHub Actions Secretsへ登録する方式** が最も簡単
5. セキュリティをさらに高める場合は、後から **Workload Identity Federation（WIF）** に移行する
6. `.github/workflows/scrape.yml` から定期実行する
7. 初回は `workflow_dispatch` による手動実行で確認し、正常動作後に `schedule` を有効化する

今回想定している処理規模（約30サイト、各サイト最大20件程度、ローカル実行約30秒）であれば、GitHub Actionsによる定期実行に適した規模である。

---

## 2. 配置・適用順序・優先順位

### 2.1 どこに置くか

想定する最低限のリポジトリ構成は以下。

```text
repository/
├── .github/
│   └── workflows/
│       └── scrape.yml
├── scraper.py
├── requirements.txt
└── .gitignore
```

Firebase関連の秘密情報を格納したJSONファイルは、リポジトリには置かない。

ローカル開発用にサービスアカウントJSONを保存する場合も、例えば以下のようにGit管理対象外とする。

```text
repository/
├── credentials/
│   └── firebase-service-account.json
└── .gitignore
```

`.gitignore` には最低限以下を追加する。

```gitignore
credentials/
*.json
.env
```

ただし、プロジェクト内に通常のJSONデータファイルが存在する場合は `*.json` を一括除外せず、認証情報ファイルのみ明示的に除外する。

例:

```gitignore
credentials/
firebase-service-account.json
.env
```

### 2.2 適用・実行順序

GitHub Actionsでは以下の順序で処理する。

```text
schedule / workflow_dispatch
        ↓
GitHub-hosted runner起動
        ↓
リポジトリ checkout
        ↓
Pythonセットアップ
        ↓
requirements.txtから依存関係をインストール
        ↓
Firebase認証情報を準備
        ↓
Pythonスクレイパー実行
        ↓
Firebaseへデータ書き込み
        ↓
ジョブ終了
```

### 2.3 優先順位

構成上の優先順位は以下とする。

1. 認証情報をGit管理しないこと
2. Firebaseへの書き込み権限を必要最小限にすること
3. PythonコードをローカルとGitHub Actionsで共通化すること
4. GitHub Actions固有処理はWorkflow側へ寄せること
5. 正常動作確認後に定期実行を有効化すること

---

## 3. 「Firebase APIキーをGitHubへ渡す」という理解について

認識は一部修正が必要である。

FirebaseのクライアントSDKで利用する `apiKey` は、Webアプリ等で利用される識別情報であり、一般にFirebase Admin SDKからサーバー側処理を実行するための主要な秘密認証情報ではない。

今回のように、

```text
GitHub Actions
    ↓
Python
    ↓
Firebaseへ自動書き込み
```

というサーバー側処理を行う場合は、通常 **Firebase Admin SDKとサービスアカウント認証** を使用する。

したがって、GitHub Actionsで安全に管理すべき中心的な情報は、APIキーそのものではなく、

- サービスアカウントの認証情報
- またはWorkload Identity Federationの設定

である。

Firebase公式ドキュメントでも、Admin SDKをサーバーから使用するためにサービスアカウントを利用する方法が案内されている。

---

## 4. 推奨する認証方式

### 4.1 初期構築で推奨: GitHub Actions Secrets + サービスアカウント

今回の規模では、まずこの方法を推奨する。

理由:

- 構成が単純
- Firebase Admin SDKの標準的な利用方法
- GitHub Actions Secretsを使えばリポジトリへ秘密鍵をコミットする必要がない
- トラブルシューティングが容易
- 既存Pythonコードへの変更が少ない

構成は以下。

```text
Firebase / Google Cloud
        ↓
サービスアカウントJSON
        ↓
GitHub Repository Secret
        ↓
GitHub Actions実行時だけ一時ファイル化
        ↓
GOOGLE_APPLICATION_CREDENTIALS
        ↓
Firebase Admin SDK
```

GitHub Actions Secretsは、リポジトリ、Environment、Organization単位で秘密情報を保管できる。Workflowから明示的に参照した場合のみ利用される。

### 4.2 より安全な方式: Workload Identity Federation

Google Cloudでは、GitHub ActionsのOIDCトークンとWorkload Identity Federationを組み合わせ、**長期間有効なサービスアカウント秘密鍵そのものをGitHubへ保存しない方式**を利用できる。

構成:

```text
GitHub Actions
      ↓ OIDC
Google Cloud Workload Identity Federation
      ↓
Google Cloud Service Account
      ↓
Firebase / Firestore
```

セキュリティ上はこちらが優れている。

ただし、

- Google Cloud IAM
- Workload Identity Pool
- Provider
- Attribute Mapping / Condition
- Service Accountの権限設定

が必要となり、初期構築コストはサービスアカウントJSON方式より高い。

今回のような個人・小規模の定期スクレイピングでは、

```text
まずSecrets方式で正常稼働
        ↓
必要に応じてWIFへ移行
```

が現実的である。

---

# 5. 初期構築手順

## Step 1. Python側の依存関係を確認する

`requirements.txt` にFirebase Admin SDKが含まれていることを確認する。

例:

```text
firebase-admin
requests
beautifulsoup4
```

既存の依存関係がある場合は削除せず、`firebase-admin` を追加する。

インストール:

```bash
pip install firebase-admin
```

必要であれば現在の環境から生成する。

```bash
pip freeze > requirements.txt
```

ただし、`pip freeze` は不要な開発用ライブラリまで固定する場合があるため、既に整理された `requirements.txt` がある場合は手動追加を優先する。

---

## Step 2. Firebase Admin SDKを利用する

Cloud Firestoreの場合の基本形:

```python
import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()

db = firestore.client()

db.collection("scraped_data").document("example").set({
    "title": "example",
    "url": "https://example.com"
})
```

重要なのは以下。

```python
firebase_admin.initialize_app()
```

で認証情報のファイルパスをハードコードしないこと。

Google Application Default Credentials（ADC）を使用すれば、実行環境側から認証情報を渡せる。

GitHub Actionsでは後述する `GOOGLE_APPLICATION_CREDENTIALS` を設定する。

### Realtime Databaseの場合

Realtime Databaseを利用している場合は以下のような形になる。

```python
import firebase_admin
from firebase_admin import db

firebase_admin.initialize_app(options={
    "databaseURL": "https://PROJECT_ID-default-rtdb.firebaseio.com/"
})

ref = db.reference("scraped_data")

ref.set({
    "example": {
        "title": "example"
    }
})
```

`databaseURL` は秘密鍵ではないため、コード中に記載してもサービスアカウント秘密鍵とは性質が異なる。

ただし、環境ごとに変更する可能性がある場合は環境変数へ分離してもよい。

---

## Step 3. サービスアカウントを準備する

Firebase ConsoleまたはGoogle Cloud ConsoleからFirebase Admin SDK用のサービスアカウントを用意する。

Firebase公式ドキュメントでは、Admin SDK利用時にサービスアカウントを使用する方法が案内されている。

秘密鍵JSONは例えば以下のような情報を含む。

```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "..."
}
```

このJSONは秘密情報である。

### 絶対に行わないこと

```text
repository/
└── firebase-service-account.json
```

としてGitへcommitしてはならない。

また、

```python
PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----..."
```

のようにPythonへ直接記述しない。

---

## Step 4. GitHub Actions Secretへ登録する

GitHubリポジトリの設定画面から登録する。

概念的な操作場所:

```text
Repository
  → Settings
  → Secrets and variables
  → Actions
  → New repository secret
```

Secret名:

```text
FIREBASE_SERVICE_ACCOUNT
```

値:

サービスアカウントJSONの**内容全体**を登録する。

例えばローカルファイルが

```text
firebase-service-account.json
```

であれば、そのファイルの中身全体をSecretへ登録する。

GitHub Actions Secretsでは秘密情報が暗号化され、Workflowから明示的に参照して利用できる。

---

# 6. GitHub Actions Workflowを作成する

作成先:

```text
.github/workflows/scrape.yml
```

まずは以下の構成を推奨する。

```yaml
name: Scheduled Web Scraping

on:
  workflow_dispatch:

  schedule:
    - cron: "17 12 * * *"
      timezone: "Asia/Tokyo"

permissions:
  contents: read

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Prepare Firebase credentials
        env:
          FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
        run: |
          printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "${RUNNER_TEMP}/firebase-service-account.json"
          echo "GOOGLE_APPLICATION_CREDENTIALS=${RUNNER_TEMP}/firebase-service-account.json" >> "$GITHUB_ENV"

      - name: Run scraper
        run: python scraper.py
```

この例では毎日日本時間12:17に実行する。

2026年8月時点のGitHub Actions公式仕様では、`schedule` にIANA timezoneを指定できるため、

```yaml
timezone: "Asia/Tokyo"
```

を使用できる。

UTCへ手動変換する必要はない。

---

# 7. 認証情報がPythonへ渡る仕組み

Workflow内の以下の処理:

```yaml
- name: Prepare Firebase credentials
  env:
    FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
  run: |
    printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "${RUNNER_TEMP}/firebase-service-account.json"
    echo "GOOGLE_APPLICATION_CREDENTIALS=${RUNNER_TEMP}/firebase-service-account.json" >> "$GITHUB_ENV"
```

によって、

```text
GitHub Secret
      ↓
Workflow実行時だけ環境変数へ展開
      ↓
Runner上の一時ファイル
      ↓
GOOGLE_APPLICATION_CREDENTIALS
      ↓
Firebase Admin SDK / Google ADC
```

となる。

このためPython側では、

```python
firebase_admin.initialize_app()
```

だけで認証できる。

GitHubリポジトリには秘密鍵ファイルを保存しない。

Runnerはジョブ終了後に破棄されるため、認証JSONも永続保存されない。

---

# 8. Firebase IAM権限を確認する

サービスアカウントには、必要なFirebase / Google Cloudリソースへ書き込める権限が必要である。

ただし、必要以上に強い権限を与えるべきではない。

GitHubもSecrets等で利用する認証情報について、必要最小限の権限を付与することを推奨している。

基本方針:

```text
必要なDBへ書き込める
          ○

プロジェクト全体を管理できる
          ×（不要なら与えない）
```

特に本番用Firebaseプロジェクトで運用する場合、スクレイピング用の専用サービスアカウントを作成し、必要な権限だけ付与することを推奨する。

---

# 9. Firestore Security Rulesとの関係

注意すべき点がある。

Firebase Admin SDKやGoogle Cloudのサーバークライアントは、通常のWeb / MobileクライアントSDKとは認証・認可の仕組みが異なる。

そのため、

```text
Firebase Security Rulesを設定している
＝
Admin SDKのサービスアカウントも同じRulesで制限される
```

とは限らない。

Admin SDK側ではIAM権限を適切に制御することが重要である。

したがって、

- Security Rules
- IAM
- サービスアカウント権限

を別物として考える。

---

# 10. GitHub Actionsの手動テスト

いきなりcronだけで試すのではなく、

```yaml
workflow_dispatch:
```

を設定しておく。

GitHub上で、

```text
Repository
 → Actions
 → Scheduled Web Scraping
 → Run workflow
```

から手動実行する。

確認項目:

1. Checkoutが成功する
2. Pythonセットアップが成功する
3. `requirements.txt` が正常にインストールされる
4. Firebase認証でエラーにならない
5. スクレイピングが成功する
6. Firebaseへ期待したデータが書き込まれる
7. 認証情報がログへ表示されていない

---

# 11. 正常稼働後に定期実行する

例えば毎日12:17 JST:

```yaml
schedule:
  - cron: "17 12 * * *"
    timezone: "Asia/Tokyo"
```

毎日午前3:17 JST:

```yaml
schedule:
  - cron: "17 3 * * *"
    timezone: "Asia/Tokyo"
```

1時間ごとの例:

```yaml
schedule:
  - cron: "17 * * * *"
    timezone: "Asia/Tokyo"
```

GitHub Actionsのスケジュール実行は厳密なリアルタイム処理ではないため、指定時刻から多少遅れる可能性がある。

スクレイピング用途で数分程度の遅延が許容できるのであれば問題になりにくい。

---

# 12. 同時実行を防止する

今回のスクレイピングは約30秒で完了するとの前提であり通常は問題にならない。

ただし、前回処理が長引いた場合に二重実行される可能性を防ぎたい場合は `concurrency` を設定できる。

```yaml
concurrency:
  group: scheduled-scraper
  cancel-in-progress: false
```

全体:

```yaml
name: Scheduled Web Scraping

on:
  workflow_dispatch:
  schedule:
    - cron: "17 12 * * *"
      timezone: "Asia/Tokyo"

permissions:
  contents: read

concurrency:
  group: scheduled-scraper
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Prepare Firebase credentials
        env:
          FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
        run: |
          printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "${RUNNER_TEMP}/firebase-service-account.json"
          echo "GOOGLE_APPLICATION_CREDENTIALS=${RUNNER_TEMP}/firebase-service-account.json" >> "$GITHUB_ENV"

      - name: Run scraper
        run: python scraper.py
```

---

# 13. スクレイピングプログラム側で追加確認すべき事項

GitHub Actionsへ移すと、ローカルPCとの環境差によって問題が発生する場合がある。

## 13.1 ファイルパス

以下のようなWindows固有絶対パスは避ける。

```python
"C:\\Users\\name\\project\\data.json"
```

相対パスまたは `pathlib` を利用する。

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
```

---

## 13.2 ブラウザを使用している場合

Requests / BeautifulSoupだけなら基本的に問題ない。

PlaywrightやSeleniumを使用している場合は、ブラウザ本体やLinux用依存ライブラリのセットアップが追加で必要になる。

この場合はWorkflowを別途調整する必要がある。

---

## 13.3 タイムゾーン

Pythonコード内で現在日時を記録している場合、GitHub-hosted runnerのOS側タイムゾーンに依存させないことを推奨する。

日本時間を記録する場合はPython側で明示する。

```python
from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("Asia/Tokyo"))
```

---

## 13.4 重複データ

定期スクレイピングでは、

```text
前回取得
↓
今回取得
↓
同じデータを再登録
```

が発生し得る。

Firebaseへ保存する際は、

- URL
- 記事ID
- Webサイト側の固有ID
- URL等から生成したハッシュ

などをFirestore Document IDとして利用し、同一データを上書きする設計にすると扱いやすい。

例:

```python
db.collection("scraped_data").document(item_id).set(data)
```

毎回自動IDを生成する方式:

```python
db.collection("scraped_data").add(data)
```

では、同じ情報を取得するたびに別ドキュメントが生成される可能性がある。

既存プログラムですでに重複管理を行っている場合は変更不要。

---

# 14. エラー時の動作

スクレイピング対象が30サイトある場合、1サイトの障害によって全処理を停止するかどうかを確認する。

例えば、

```python
for site in sites:
    scrape(site)
```

で例外が未処理の場合、途中の1サイトで失敗するとWorkflow全体が終了する。

設計として、

```text
1サイト失敗
 ↓
ログ記録
 ↓
残りサイトを処理
```

としたい場合は、Python側でサイト単位の例外処理が必要である。

ただし、これは既存スクレイパーが既に対応済みなら変更不要。

---

# 15. ログに秘密情報を出さない

以下は避ける。

```python
print(firebase_credentials)
```

Workflowでも以下のようなデバッグは実施しない。

```yaml
run: echo "${{ secrets.FIREBASE_SERVICE_ACCOUNT }}"
```

GitHubはSecretsのマスキング機構を持つが、変換された秘密値等について完全なマスキングを保証するものではない。

そのため、そもそもログへ出力しないことが重要である。

---

# 16. GitHub Actionsの権限を最小化する

今回のWorkflowはリポジトリへpushする必要がないため、

```yaml
permissions:
  contents: read
```

で十分である。

不要な、

```yaml
contents: write
```

は付与しない。

GitHub公式も認証情報・トークンに必要最小限の権限を付与することを推奨している。

---

# 17. GitHub Actions自体のセキュリティ

GitHub公式は、第三者Actionを利用する際、特定のcommit SHAへ固定する方式が最も安全な不変参照であるとしている。

例えば簡易構成では、

```yaml
uses: actions/checkout@v4
uses: actions/setup-python@v5
```

で十分扱いやすい。

より厳格に管理する場合は、確認済みcommit SHAへ固定する。

```yaml
uses: actions/checkout@<FULL_COMMIT_SHA>
```

今回の初期構築ではGitHub公式Actionだけを使い、不要な第三者Actionを増やさないことを推奨する。

---

# 18. Workload Identity Federationへ移行する場合

サービスアカウントJSON方式が正常動作した後、必要であればWIFへ変更できる。

WIFでは長期秘密鍵をGitHub Secretsに保存しなくてよい。

Workflow側では概ね以下の構成となる。

```yaml
permissions:
  contents: read
  id-token: write

steps:
  - name: Checkout repository
    uses: actions/checkout@v4

  - name: Authenticate to Google Cloud
    uses: google-github-actions/auth@v3
    with:
      workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
      service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: "3.13"

  - name: Install dependencies
    run: pip install -r requirements.txt

  - name: Run scraper
    run: python scraper.py
```

この場合、

```text
FIREBASE_SERVICE_ACCOUNT
```

という秘密鍵そのものが不要になる。

代わりにGoogle Cloud側で、

1. Workload Identity Pool作成
2. GitHub用OIDC Provider作成
3. GitHub organization / repositoryをAttribute Condition等で制限
4. サービスアカウント作成
5. Workload Identity User権限設定
6. Firebase / Firestore用IAM権限設定

を行う。

GoogleはGitHub ActionsとのWIFについて、長期サービスアカウントキーを外部へ持ち出さず短期認証情報を利用できる方式として案内している。

### 導入コスト

サービスアカウントJSON:

```text
低
```

WIF:

```text
中
```

### セキュリティ

サービスアカウントJSON:

```text
○
GitHub Secretsで適切に管理すれば実用的
ただし長期秘密鍵を保有する
```

WIF:

```text
◎
長期秘密鍵をGitHubへ保存しない
```

### 可逆性

WIFへ移行してもPython側でADCを使用していれば、

```python
firebase_admin.initialize_app()
```

を変更する必要は基本的にない。

したがって、最初からADCを使う構造にしておけば認証方式の移行が容易である。

---

# 19. 推奨する最終構成

今回の用途では、まず以下とする。

```text
GitHub Repository
│
├── scraper.py
├── requirements.txt
└── .github/
    └── workflows/
        └── scrape.yml
              │
              ├── schedule
              ├── workflow_dispatch
              ├── Python setup
              ├── pip install
              ├── GitHub Secret読み込み
              └── scraper.py実行
                       │
                       ↓
                Firebase Admin SDK
                       │
                       ↓
               Firestore / Realtime DB
```

GitHub:

```text
Repository Secret
└── FIREBASE_SERVICE_ACCOUNT
```

ローカル:

```text
credentials/
└── firebase-service-account.json

.gitignore
└── credentials/
```

---

# 20. 実際の導入順序

以下の順番で進める。

- [ ] 既存スクレイパーがローカルで正常動作することを確認する
- [ ] `requirements.txt` に `firebase-admin` が含まれていることを確認する
- [ ] Firebase接続処理を `firebase_admin.initialize_app()` を使うADC方式にする
- [ ] サービスアカウントを用意する
- [ ] サービスアカウントに必要最小限のIAM権限を設定する
- [ ] 認証JSONを `.gitignore` の対象にする
- [ ] 認証JSONが過去にGitへcommitされていないことを確認する
- [ ] GitHub Actions Secret `FIREBASE_SERVICE_ACCOUNT` を登録する
- [ ] `.github/workflows/scrape.yml` を作成する
- [ ] `workflow_dispatch` から手動実行する
- [ ] Actionsログを確認する
- [ ] Firebaseにデータが登録されたことを確認する
- [ ] 同じWorkflowをもう一度実行し、重複登録の挙動を確認する
- [ ] `schedule` による定期実行を有効化する
- [ ] 翌回の定期実行結果をActions画面とFirebase双方で確認する

---

# 21. 推奨する完成版 `scrape.yml`

サービスアカウントJSON方式であれば、まず以下を完成形とする。

```yaml
name: Scheduled Web Scraping

on:
  workflow_dispatch:

  schedule:
    - cron: "17 12 * * *"
      timezone: "Asia/Tokyo"

permissions:
  contents: read

concurrency:
  group: scheduled-web-scraping
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Prepare Firebase credentials
        env:
          FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
        run: |
          printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "${RUNNER_TEMP}/firebase-service-account.json"
          echo "GOOGLE_APPLICATION_CREDENTIALS=${RUNNER_TEMP}/firebase-service-account.json" >> "$GITHUB_ENV"

      - name: Run scraper
        run: python scraper.py
```

`timeout-minutes: 10` は、通常約30秒で終わる処理が何らかの理由でハングした場合に、長時間Runnerを占有し続けることを防ぐために設定している。

---

# 22. 最終判断

今回の用途で追加対応が必要なのは、主として以下の5点である。

1. **Firebaseの認証情報をGitへ保存しない**
2. **Firebase Admin SDKを利用する**
3. **GitHub Actions SecretsまたはWIFから認証する**
4. **サービスアカウントのIAM権限を必要最小限にする**
5. **ローカル環境とLinux GitHub runnerとの差異を確認する**

特に認証については、

```text
Firebase APIキーをGitHub Secretsへ入れる
```

というより、

```text
Firebase Admin SDK
+
サービスアカウント認証
+
GitHub Actions Secrets
```

と理解するのが適切である。

最初の実装ではサービスアカウントJSON方式が最も単純であり、運用上さらにセキュリティ要求が高まった場合にWorkload Identity Federationへ移行する。

---

# 参考文献

- GitHub Docs — Secrets  
  https://docs.github.com/en/actions/concepts/security/secrets

- GitHub Docs — Secrets reference  
  https://docs.github.com/en/actions/reference/security/secrets

- GitHub Docs — Workflow syntax for GitHub Actions  
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

- GitHub Docs — Events that trigger workflows  
  https://docs.github.com/actions/using-workflows/events-that-trigger-workflows

- GitHub Docs — Secure use reference  
  https://docs.github.com/en/actions/reference/security/secure-use

- Firebase — Add the Firebase Admin SDK to your server  
  https://firebase.google.com/docs/admin/setup

- Firebase — Get started with Firestore Standard edition using server client libraries  
  https://firebase.google.com/docs/firestore/quickstart-server

- Firebase — Get data with Cloud Firestore  
  https://firebase.google.com/docs/firestore/query-data/get-data

- Firebase — Introduction to the Admin Database SDK  
  https://firebase.google.com/docs/database/admin/start

- Google Cloud — Workload Identity Federation  
  https://cloud.google.com/iam/docs/workload-identity-federation

- Google Cloud — Configure Workload Identity Federation with deployment pipelines  
  https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines

- google-github-actions/auth  
  https://github.com/google-github-actions/auth
