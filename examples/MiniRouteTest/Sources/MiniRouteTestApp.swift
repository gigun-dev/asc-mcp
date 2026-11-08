import SwiftUI

@main
struct MiniRouteTestApp: App {
    var body: some Scene {
        WindowGroup { RouteTestView() }
    }
}

struct RouteTestView: View {
    @State private var confirmationCount = 0

    private var buildLabel: String {
        let info = Bundle.main.infoDictionary ?? [:]
        let version = info["CFBundleShortVersionString"] as? String ?? "?"
        let build = info["CFBundleVersion"] as? String ?? "?"
        return "Version \(version) · Build \(build)"
    }

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: confirmationCount == 0 ? "iphone" : "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundStyle(confirmationCount == 0 ? Color.accentColor : .green)
                .accessibilityHidden(true)
            Text("Mini Route Test")
                .font(.largeTitle.bold())
            Text(buildLabel)
                .font(.headline.monospacedDigit())
            Text("Mac mini → 非公開配布 → このiPhone")
                .multilineTextAlignment(.center)
            Button("動作を確認") { confirmationCount += 1 }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("confirmInstallButton")
            Text(confirmationCount == 0 ? "ボタンを押して動作を確認してください" : "動作確認済み（\(confirmationCount)回）")
                .accessibilityIdentifier("confirmationStatus")
            Text("通信・データ収集・永続保存は行いません")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(28)
    }
}

#Preview { RouteTestView() }
