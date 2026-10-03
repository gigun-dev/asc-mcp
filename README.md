# asc-mcp

ASC CLIをクラウドから使うための認証付きMCPサービス。現在は、登録済みiOSアプリのPR/commitをMacでビルド・署名し、認証付き固定ページから私的に配布する3ツールを提供する。ASC全コマンドの公開は行っていない。

自分が別環境で使え、他の人も設定を差し替えて再構築できることを目標とする。公開コードに本人のアカウント・ドメイン・署名情報を埋め込まない。

## 構成

MCP client → Cloudflare Access Managed OAuth → Workers MCP → GitHub Actions → macOS runner / ASC → private R2 / install page → Bark

- `src/`: `list_apps`、`build_app(project, pr|commit)`、`get_build(job_id)`。
- `infra/`: D1、非公開R2、Access / Managed OAuth。Worker本体・custom domain / DNSはWranglerが管理する。
- `.github/workflows/build.yml`: **非公開の制御repoでのみ**実行する固定workflow。
- `scripts/run.py`: 登録済みproject/schemeで、SHA固定checkout → archive → Ad Hoc export → ASC署名検証 → publish。
- `distribution/`: 既存のAccess・10分署名URL・固定ページ・Bark AES通知を引き継ぐ。ASC distributeへの全面置換は未検証。

## 必要なもの

- Cloudflareアカウントとドメイン、GitHub App、非公開の制御repo。
- Xcodeが対象アプリに対応するMac、署名可能なApple Developer Programのアカウント・登録端末。
- ASC **5.9.2**、XcodeGen（project.ymlでprojectを生成するアプリ）、Node **24**、npm、Python 3、OpenTofu **1.12.6**。Bark暗号化通知を使う場合はage・openssl。
- Mac runnerは専用ユーザー・専用キーチェーンを推奨。XcodeのRun Scriptもコードとして実行されるため、作者を許可しただけでコード隔離が保証されるわけではない。

## 初期構築

1. 本repoをcloneし `npm ci`。`npm run check` と `python3 -m unittest discover -s tests -p '*_test.py'` を実行。
2. `infra/example.tfvars`をgitignoredの `infra/config.tfvars`へコピーして値を差し替える。Cloudflare provider用 `CLOUDFLARE_API_TOKEN`（Access・D1・R2の対象リソースへの編集権限）を設定する。加えて、独立した強い `TF_VAR_state_passphrase` を環境へ設定する。
3. `tofu -chdir=infra init` → `tofu -chdir=infra plan -var-file=config.tfvars -out=change.tfplan` → 内容確認後 `tofu -chdir=infra apply change.tfplan`。state/planは暗号化し、Gitへ入れない。暗号鍵を別途バックアップする。複数環境/担当者で運用するときはロック対応backendも設定する。
4. `config.example.json`を `config.local.json`へコピー。Tofuのdatabase ID・MCP audience・install audienceを反映し `node scripts/configure.mjs`。生成される2つのproduction Wrangler設定はgitignored。
5. [GitHub App設定手順](docs/github-app.md)に沿ってAppを登録し、対象repoだけへinstall。制御repoのActions read/write、アプリrepoのContents read / Pull requests readを付与。App ID・installation ID・PKCS#8 PEM秘密鍵をMCP Workerの `GITHUB_APP_ID` / `GITHUB_INSTALLATION_ID` / `GITHUB_APP_PRIVATE_KEY` secretsへ設定する。Apple用APIキーは今回不要。
6. `npx wrangler d1 migrations apply asc-mcp-jobs --remote --config wrangler.production.json`、`npx wrangler deploy --config wrangler.production.json`。
7. 配布Workerへ `DOWNLOAD_SECRET`（ランダム値）を設定し、`npx wrangler deploy --config distribution/wrangler.production.json`。署名検証を配備する前にdownloadパスのAccess例外を利用しない。
8. **非公開**制御repoを作り、`.github/workflows/build.yml`だけを配置する。varsの `SERVICE_REPOSITORY` に本サービスrepo、`SERVICE_REVISION` に検証済み40桁commit SHAを設定する。ビルドロジックはこの固定版をcheckoutし、制御repoへ複製しない。公開repoの外部PRからrunnerを動かさない。miniへGitHub公式runnerを登録して `asc-mcp` labelを付ける。ASC・Xcode・署名をrunnerの実行ユーザーで `asc xcode doctor` と実archive/exportで確認する。SSH/GUIで署名結果が異なる場合はここで解決する。
9. 制御repoのvarsに `PROJECTS_JSON`（configのprojects部分）、`CLOUDFLARE_ACCOUNT_ID`、`OTA_PUBLIC_ORIGIN`、`OTA_R2_BUCKET`を設定。配布用Wrangler設定はworkflowがvarsから生成する。secretsのCloudflare tokenはR2対象bucketへの書込だけに限定。privateアプリrepo取得用 `SOURCE_TOKEN` はContents readへ限定する。実行時の短命GitHub App tokenを使う形への移行は運用受け入れで確認する。
10. Bark利用時は既存の通知設定を `BARK_ENV` secretへ登録するか、runnerのage暗号化設定ファイルを `BARK_ENV_FILE` varで指定する。通知設定をXcodeプロセスへ渡さない。秘密情報をworkflowやログへ貼らない。
11. ChatGPT / Claude / Codexへ `https://YOUR_MCP_HOST/mcp` を追加しAccessログイン。Managed OAuthの許可callback URIは使うクライアントの実値だけを登録する。

アプリ追加はconfigのprojectsにrepo・scheme・project・teamId・trustedAuthorsを追加し、Worker設定とrunner側設定の両方へ反映する。`commit`はtrustedRefの履歴上の40桁SHAのみ。未merge変更は同repo・許可作者・open PRだけを受付時のhead SHAへ固定する。

## 完了の確認

- 未認証・別audienceのJWTは拒否される。認証後3ツールが取得できる。
- fork PR / 未許可作者 / 任意shellやproject pathは拒否される。
- build_appはjob IDを返し、get_buildで本人のjobだけを読める。
- 失敗時にlatest配布物を切り替えず、dispatch応答喪失を自動再送しない。
- 成功時にIPA検証・配布・Bark通知・実機installまで確認する。
- 元環境のconfig/秘密情報を流用せず、別設定の新しい環境で同じ手順を実行する。

Managed OAuthとD1はIaCで配備済み。3クライアントのOAuth、mini常駐runner、無人署名、別環境での構築は未確認。既存の配布サービスを併用する場合は `manage_distribution=false` とし、既存の配布audience/bucketを設定する。既存installサービスのリソースはまだ移管せず、運用切替時にdotfilesからstateを移す。両方から同じAccessリソースを管理しない。

## ライセンスと参照

MIT。配布コードはgigun-dev/claude-codeのカスタムOTA実装から移植。元のOTA pluginは [mariosaputra/ota-deploy](https://github.com/mariosaputra/ota-deploy) を基にしており、著作権表示を保持する。

- [ASC CLI](https://github.com/rorkai/App-Store-Connect-CLI) / [作者のskill plugin](https://github.com/rorkai/app-store-connect-cli-skills)
- [Access Managed OAuth](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/)
- [Self-hosted runnerの注意](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
