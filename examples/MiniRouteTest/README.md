# MiniRouteTest

iPhoneへのAd Hoc配布を受け入れるための最小アプリ。インストール後に画面のVersion/Buildと
「動作を確認」ボタンの反応を確認する。Widget・Watch・通知・永続保存は持たない。

2026-10-20にminiで検証した既存sourceを変更せず保全した。元の作業directoryは
`/Users/gigun/Documents/Codex/2026-10-20/task-4/MiniRouteTest`。取り込み前はGit管理されて
いなかったので、このrepoへの取り込みcommit以降をsource revisionとする。旧archiveへ
後からこのcommitのprovenanceを付けない。

| Source | 元sourceと取り込みsourceで一致したSHA-256 |
|---|---|
| `project.yml` | `c3a2d8bf000bb8788a5bf8150ea0f1743d0daf4e7fff81e4c163aa21f02440c9` |
| `Sources/MiniRouteTestApp.swift` | `9b41f00fd90b09938dbc0dd14ec2b6e867833f226935d183855166f4e69fad19` |

## 固定commitから未署名archiveを作る

miniで、レビュー済み40桁commitを`SOURCE_SHA`へ指定して独立checkoutする。下記は
署名・Apple API・uploadを実行しない。ソースcheckoutとarchive出力先は新規pathを使う。
ASCはminiで確認した絶対pathを指定し、実行前にversionを記録する。

```sh
SOURCE_SHA='<取り込み後にレビューした40桁commit>'
git clone --no-checkout https://github.com/gigun-dev/asc-mcp.git MiniRouteTest-source
git -C MiniRouteTest-source checkout --detach "$SOURCE_SHA"
git -C MiniRouteTest-source rev-parse HEAD
cd MiniRouteTest-source/examples/MiniRouteTest
xcodegen generate --spec project.yml
/Users/gigun/.local/bin/asc version
xcodebuild -version
/Users/gigun/.local/bin/asc xcode archive \
  --project MiniRouteTest.xcodeproj --scheme MiniRouteTest \
  --archive-path "$PWD/../../work/MiniRouteTest.xcarchive" \
  --xcodebuild-flag=-destination --xcodebuild-flag=generic/platform=iOS \
  --xcodebuild-flag=CODE_SIGNING_ALLOWED=NO \
  --xcodebuild-flag=CODE_SIGNING_REQUIRED=NO \
  --xcodebuild-flag=CODE_SIGN_IDENTITY= --output json
```

生成した`.xcodeproj`は追跡しない。archive、DerivedData、profile、IPA、Keychainとpasswordも
commitしない。archive検査で単一app、arm64、bundle ID `dev.gigun.miniroutetest`、想定version/build、
extensionなし、未署名状態を確認し、source SHAとarchive digestを別々に記録する。

## 署名・配布へ渡す条件

`project.yml`のTeamは既存検証用の`KK42DL23GH`であり、このファイルが署名利用を認可する
わけではない。既存の`dev.gigun.mcphost`用Ad Hoc profileはこのbundle IDと一致しない。
対象iPhone、Team、certificate、期限、entitlement、アプリIDが一致する資材で標準signing runによるmanual exportを行い、
標準prepareでIPAを検証する。Development wildcard profileをAd Hoc用に代用しない。

未署名archiveの構造検査や合成テストの成功から、署名可能・配布可能・iPhone起動成功とは
判定しない。工程と実行主体、残る依存はrepoの`docs/ad-hoc-delivery.md`を参照する。
