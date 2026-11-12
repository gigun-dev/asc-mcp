# iPhoneから依頼するAd Hoc OTA配布

iPhoneから依頼し、miniでビルド・署名したアプリを通知リンクからインストール・起動することを目指す。初回は拡張なしのMiniRouteTestで検証する。App Store提出・TestFlight、WidgetやWatchを含む複数ターゲットは対象外。

## 方針と実装の状態

履歴ツールで読めた過去の委譲文は、本人が既存GitHub Actions → mini → ASC標準の署名・OTA経路を受理し、独自sudo・rolesや新Remote MCPは進めない方針だったと報告している。元の本人発言は取得できておらず、これは二次記録である。別ユーザーやrunnerの具体的な配置案を、本人承認済み・配置済みと扱わない。

`scripts/ad_hoc.py`には標準ASCの段階実行を実装した。ローカルのDistribution PKCS#12、password file、対象アプリと端末に適合するAd Hoc profileを使う場合、Apple API認証を必須としない。

- `export`はASC `signing run`内で固定のmanual `release-testing` exportを実行する。任意child、追加xcodebuild flag、automatic provisioning updateは受け付けない。
- `prepare`は署名済みIPAをASC標準の検査に通してbundleを生成する。未署名IPAの`inspect`成功は配布可能という意味ではない。
- `publish`はbundleのIPAをcredentialなしで再度prepareし、ASC標準publishによるdescriptorとpayloadの検証を経てprivateリンクを発行する。期限はページ24時間、manifestとIPAは追加猶予1時間。リンクは秘密として扱う。

ASCが一時Keychainとprofileを管理する。独自Keychain daemonやone-use protocol、成功時の証明書失効は追加しない。stdoutとstderrはcreate-onlyの0600ファイル、署名receipt・publish receipt・リンクは指定resultに隣接するファイルに保存する。publishのS3 credentialはpublish子processにだけ渡す。

この段階実行は**既存Actionsの本番経路に接続されていない**。現行`scripts/run.py`は同一job・同一UIDでbuild/export/prepareを行い、既存publisherを呼ぶ経路であり、上記adapterそのものではない。子processへの環境変数を制限しても、同じUIDのhome・Keychain・他processは隔離されない。build主体から署名主体への検査済み成果物の受渡し、runner、資格情報供給、配置先と運用は未実装・未検証である。`asc-build`と`asc-sign`の存在だけでは分離の成立を証明しない。

標準private publishと既存Access固定ページ・Bark通知の互換性も未確認。実際のリンクartifactと通知payloadを検証してから接続する。通知受付、iPhoneへの表示、インストール、起動はそれぞれ別の結果として確認し、通知失敗だけで再署名しない。

## 確認済みの証拠

2026-11-09の読み取りでは、miniの公式runner `mini-asc-mcp`はonline/idle、`gigun` UID501のGUI LaunchAgentで`SessionCreate=false`だった。Xcode 26.3 (17C529)、ASC `/Users/gigun/.local/bin/asc` 5.17.1。runnerのPATHには`.local/bin`とNixのユーザープロファイルが含まれ、非対話SSHのPATHではascを解決できなかった。control repoの`SERVICE_REVISION`は`081b0641df043a5a2cf1ac75eb734ca5899f2855`、最新成功runは2026-10-04の`37238379770`。これらは現在の署名成功を示さない。

2026-11-12の再監査ではrunnerはonline/idleで、保存PATHはsystem 5要素、home 1要素、Nix user profile 1要素だった。Nix要素だけを外す候補PATHでも`python3`、`xcodebuild`、`git`、`asc`は解決し、`node`と`npm`だけが失われる。build workflowがcheck workflowと異なり`actions/setup-node`を呼ばず、hostのNodeを暗黙に使っていたことが原因だった。build workflowもcheckと同じ完全SHAのactionでNode 24.20.0を用意し、host PATHからNodeの供給責務を外す。実機PATHの切替は、このworkflowをprivate control repoへ反映して固定SHAのbuildを受入した後に行う。

公開templateとprivate control repoへ反映後、登録済みprojectの信頼branchを完全SHAに解決して実行した。PATH切替前後の2回とも`setup-node`、`npm ci`、Xcode archiveは成功し、exportで現GUI runner contextにDistribution identityと有効なXcode accountが無いため停止した。Node由来の失敗は無く、切替後も同じ署名境界まで到達したため、runnerの保存PATHからNix user profile 1要素を除去した。残した6要素、runnerのonline/idle、値非表示のNix参照監査を確認した。これはarchive工程とPATH移行の受入であり、署名・publish・OTA配布の成功ではない。

同じGUI security sessionでのidentity列挙ではApple Development 1件、Distributionは見えなかった。SSHだけで得た0件を全sessionの不在と扱わない。読み取れたprofileはDevelopment 2件とMCPHost Ad Hoc 1件で、MiniRouteTestへの適合と本人のiPhoneとの一致は未確定。`asc --read-only auth doctor`はgigunにASC保存認証がないと報告したが、別ユーザーの状態は示さない。

取り込みcommit `fc92004edf24f88fe124a8c7c71d51d558498a1c`のgit archiveをminiに展開し、tarのpax commitとSHA-256 `9ae824464b3751816e7b177549584c2f0c39733171204e60f64de11100120b7b`を照合した。Xcode 26.3 / SDK 26.2 / ASC 5.17.1で未署名Release archiveを1回作成した。`dev.gigun.miniroutetest`、1.0 build 1、arm64、単一app、extensionなしで、embedded profileと署名はない。archive digest（sorted相対path + NUL + file SHA256 + newline）は`de54d7fd0b53fcf86f9c6a55e11c4b809136a9207719fcdb63167b75c3e12a0c`、7 files。archiveはminiの`Library/Caches/asc-mcp-verification/fc92004edf24-bc153d39/`、private receiptとlogはローカルworkに保持する。信頼済みsourceをgigunで実行したsmokeであり、隔離builder・署名・配布・実機起動の受入結果ではない。

XcodeGenは`USER`/`LOGNAME`を除いた環境で失敗し、実UIDから得た2値だけを戻す対照で成功した。共通の非秘密環境許可リストはその2値を含む。旧archiveの構造検査はpassedでも署名適格性は未評価。ASCの未署名IPA検査はprofile欠落・署名未検証を示した。

今回の固定commitのarchiveから作った未署名IPAを新しい`ad_hoc.py prepare`へ渡す実走でも、embedded profile missingでexit 1となり、bundleは作られなかった。元archiveのdigestは前後で一致し、診断出力は0600だった。これは不適合の拒否確認であり、適合IPAでの署名・publish成功は未確認である。

過去のarchive・Ad Hoc署名・R2配布・Bark受付成功は履歴として扱う。現在の署名資材、runner、iPhoneへのインストール・起動の証拠には使わない。旧候補の主要10ファイルは`work/mini-route-legacy/`に保全し、`preserved-hashes.json`でremote/local SHA-256を照合した。秘密資材やIPAは含めていない。

## 署名資材の確認

旧レビュー記載の`/Users/asc-sign/private-import/realbind-distribution.p12`と`/Users/asc-sign/Library/Keychains/mini-route-signing.keychain-db`は候補パスで、当時gigunからPermission deniedだったため存在・利用可能性は未確認。password fileの既存パスも確定していない。`/Users/asc-sign/signing`と`/Users/asc-sign/delivery`は過去の配置案であって、実在する資材の所在ではない。profileに含まれる公開証明書だけでは秘密鍵を使えると証明できない。

所有者が対象ユーザー自身の環境で、読み取り専用inventoryを実行できる。出力先は既存ファイルを上書きせず0600で作成される。

```sh
python3 scripts/signing_inventory.py \
  --asc /Users/gigun/.local/bin/asc \
  --identity-path /Users/asc-sign/private-import/realbind-distribution.p12 \
  --identity-path /Users/asc-sign/Library/Keychains/mini-route-signing.keychain-db \
  --output /private/path/signing-inventory.json
```

実行するユーザーとsecurity sessionのidentity件数、候補パスの存在状態、ユーザーのprofileディレクトリにあるTeam・application identifier・期限・端末数を報告する。秘密鍵、password、端末UDIDを出力せず、importやアカウント変更も行わない。profileはmetadataの抽出のみで、trust・秘密鍵の対応・対象iPhoneの登録・署名可能性は判定しない。候補パスを指定しなければ任意の保護領域を探索しない。**asc-sign本人の環境ではまだ実行していない**。アクセス拒否は不在を意味しない。

今回gigunのSSH contextでこのinventoryを実走し、profile 3件、旧P12候補は`inaccessible/EACCES`、identityは0件、出力0600を確認した。同じ出力先での再実行はEEXISTで拒否された。`sudo -n -l`もpassword requiredで、所有者の読み取り監査へ進むにはminiでの管理者認証が必要だった。ユーザーのshellを変更せず、所有者としてPythonを明示実行する方法を先に検討する。

以前、asc-signのshellを`/usr/bin/false`から`/bin/zsh`へ変更する操作が限定承認されたと記録されているが、10月25日時点では管理者認証が必要で未実行だった。現在の状態を確認し、必要な本人操作を決める。既存のP12と適合profileを使えなければ、所有者と不足を確認して取得方法を決める。新しい証明書や認証を先に作らない。

## 完走に残る作業

1. 署名所有者contextで資格情報を値非表示監査し、Distribution identity、profile、対象iPhoneの適合を確定する。
2. build・sign・publishのOS主体と権限、検査済みarchiveの受渡し、拒否条件と復旧方法を配置する。同一UIDの工程分割を隔離と扱わない。
3. 固定sourceから署名なしarchiveを作り、source SHA、digest、bundle構造を検査してsign主体へ渡す。
4. sign主体だけでmanual Ad Hoc exportし、automatic provisioning、不一致、期限切れを拒否する。
5. 署名済みIPAをASC prepareで再検査してprivate publishし、artifact digestと期限付きURLを確認する。
6. Bark通知から本人のiPhoneでインストール・起動・ビルド一致を確認し、iPhoneからの依頼・結果取得まで通す。
7. miniのロック・再起動後のrunnerとKeychain、期限切れ・認証失効・配布失敗からの復旧を検証する。GUI login Keychainに依存する現runnerを無人復帰可能と仮定しない。

配布の実装と証拠はasc-mcp、ホスト設定とTailscale・Nix撤去はdotfiles、呼び出し方法はclaude-code plugin、アプリ固有のcommitと起動証拠はアプリrepoが所有する。
