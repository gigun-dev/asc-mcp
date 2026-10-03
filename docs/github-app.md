# GitHub Appの登録

[New GitHub App](https://github.com/settings/apps/new)でこのサービス用Appを作る。

- 名前はアカウント内で識別できるもの（例 asc-mcp-あなたの名前）。Homepage URLは自分のサービスrepo。
- Webhookは今回は使わないためActiveを外す。ユーザーOAuthのcallback設定は不要（MCP認証はCloudflare Access）。
- Repository permissionsはActions read/write、Contents read、Pull requests read。その他は追加しない。
- Install可能なアカウントは自分だけにし、非公開制御repoと対象アプリrepoだけを選択する。

登録後にApp ID・installation IDを控える。installation IDは対象installationの設定URLから確認できる。Private keyを発行してダウンロードし、チャットやGitへ貼らず保管する。

GitHubの鍵がPKCS#1の場合は `openssl pkcs8 -topk8 -nocrypt -in downloaded.pem -out app-pkcs8.pem` でPKCS#8へ変換する。WorkerのsecretにはPKCS#8を用いる。

```sh
npx wrangler secret put GITHUB_APP_ID --config wrangler.production.json
npx wrangler secret put GITHUB_INSTALLATION_ID --config wrangler.production.json
npx wrangler secret put GITHUB_APP_PRIVATE_KEY --config wrangler.production.json < app-pkcs8.pem
```

Appの登録と秘密鍵の発行が終わったら、値をチャットへ送る必要はない。どこに保管したか、またはWorkerへ登録済みかだけを伝える。
