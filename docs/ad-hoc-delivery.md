# iPhoneから依頼するAd Hoc OTA配布

目標は、iPhoneから依頼し、miniでビルド・署名したアプリを通知リンクからインストール・起動すること。日常の実行にMacBookを必要としない。App Store提出・TestFlightは今回の対象外。

## 証拠の現在地

旧経路のarchive・Ad Hoc署名・R2配布・Bark受付成功は過去の記録として保持する。本人提示の現在地は、新しい権限分離方式で未署名Release archive、OTAと入力検証の合成テストまで成功。新方式の該当commit・実行ログは再開時に特定する。iPhoneへの実際のインストール・起動は未確認で、過去の成功から現在の署名資材やrunnerの稼働を推定しない。

## 初回完走までの順序

1. miniのrunnerの実行ユーザー・起動方法・PATH・Xcodeを確認する。証明書と秘密鍵の対応、profile期限、Team・アプリID・対象iPhoneの登録を照合する。利用可能な資材、不足、本人操作が必要な箇所が明確になれば完了。
2. build・sign・publishの実行主体、入力、権限、拒否条件、復旧方法を定義する。buildに署名鍵や配布資格情報を渡さず、signは検査済み成果物、publishは検証済みIPAだけを受け取る。同一ホスト・同一UIDで残るリスクを明記する。mini-vmとminiのgigun相互SSHも、この境界の前提に含める。
3. 所有repoと固定commitを特定してMiniRouteTestをビルドする。archiveと署名資材を照合しAd Hoc exportする。アプリID・対象端末・期限・entitlement・署名の整合性を検証し、不一致を拒否できる、対象iPhone用IPAができれば完了。
4. manifest・IPAの取得方法とアクセス制限を確認してR2配布・Bark通知を行う。本人がiPhoneでインストール承認と起動を行い、通知・インストール・起動・対象ビルドの一致を別々に確認する。
5. 採用するエージェントからActions起動・結果取得を接続する。repo・commit・認証・重複実行・失敗通知を検証し、MacBookの操作なしでiPhoneの依頼から配布リンク取得まで完走すれば完了。
6. miniのロック・再起動後のrunnerとKeychain、証明書期限切れ・認証失効・配布失敗の通知と復旧を検証する。Nix撤去前にrunnerのPATH依存を置換する。無人で動く範囲と本人操作の条件が明確で、再起動後も再実行できれば完了。

## 所有と後続

配布の進行と検証記録はasc-mcp、ホスト設定とTailscale・Nix撤去はdotfiles、呼び出し方はclaude-code plugin、アプリ固有のcommitと起動証拠はアプリrepoが持つ。MiniRouteTestの所有repoは未特定。現在のscripts/run.pyの同一job・同一UID実行を、新方式の隔離完了と扱わない。

初回完走後に複数クライアント、Widget・Watch等の複数ターゲット、別環境での再構築を検討する。現在のGUI login Keychainに依存するrunnerを、そのまま再起動後も無人復帰できる構成と扱わない。
