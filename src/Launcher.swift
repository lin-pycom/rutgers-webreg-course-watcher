import AppKit
import SwiftUI

@main
struct WebRegWatcherApp: App {
    var body: some Scene {
        WindowGroup {
            WatcherWindow()
                .frame(minWidth: 760, minHeight: 620)
        }
        .windowResizability(.contentSize)
    }
}

@MainActor
final class WatcherModel: ObservableObject {
    @Published var output = "准备就绪。点击“开始监听”后，这里会显示当前课程和运行日志。"
    @Published var running = false
    private var process: Process?
    private var outputPipe: Pipe?

    func start() {
        guard !running else { return }
        guard let script = Bundle.main.url(forResource: "watcher_dynamic", withExtension: "py") else {
            append("应用包中找不到 watcher_dynamic.py。")
            return
        }
        let homePath = FileManager.default.homeDirectoryForCurrentUser.path
        let pythonPaths = [
            "/opt/homebrew/bin/python3", "/usr/local/bin/python3",
            "/opt/anaconda3/bin/python3",
            homePath + "/miniconda3/bin/python3",
            homePath + "/anaconda3/bin/python3",
            "/usr/bin/python3"
        ]
        guard let python = pythonPaths.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
            append("没有找到 Python 3。请先安装 Python 3。")
            return
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: python)
        task.arguments = [script.path]
        task.currentDirectoryURL = script.deletingLastPathComponent()
        task.environment = ProcessInfo.processInfo.environment.merging([
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/opt/anaconda3/bin:\(homePath)/miniconda3/bin:\(homePath)/anaconda3/bin:/usr/bin:/bin"
        ]) { _, new in new }
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        outputPipe = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.append(text) }
        }
        task.terminationHandler = { [weak self] task in
            Task { @MainActor in
                self?.running = false
                self?.append("\n监听进程已结束（状态码 \(task.terminationStatus)）。")
            }
        }
        do {
            try task.run()
            process = task
            running = true
            append("\n正在启动监听程序…")
        } catch {
            append("启动失败：\(error.localizedDescription)")
        }
    }

    func stop() {
        guard let process, process.isRunning else { return }
        append("\n正在停止监听…")
        process.interrupt()
    }

    private func append(_ text: String) {
        output += text
        if output.count > 50_000 { output = String(output.suffix(35_000)) }
    }
}

struct WatcherWindow: View {
    @StateObject private var model = WatcherModel()
    private let red = Color(red: 0.66, green: 0.04, blue: 0.19)

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 16) {
                Text("R").font(.system(size: 42, weight: .black, design: .serif))
                    .foregroundStyle(.white).frame(width: 58, height: 58)
                    .overlay(Circle().stroke(.white.opacity(0.7), lineWidth: 2))
                VStack(alignment: .leading, spacing: 4) {
                    Text("Rutgers WebReg 选课助手").font(.system(size: 25, weight: .bold))
                    Text("课程空位提醒 · Safari 注册页自动提交").font(.system(size: 13)).opacity(0.9)
                }
                Spacer()
                Label(model.running ? "正在监听" : "已停止",
                      systemImage: model.running ? "dot.radiowaves.left.and.right" : "pause.circle")
                    .font(.system(size: 14, weight: .semibold))
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(.white.opacity(0.16), in: Capsule())
            }
            .foregroundStyle(.white).padding(24).background(red)

            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 12) {
                    Button(action: model.start) {
                        Label("开始监听", systemImage: "play.fill")
                            .frame(width: 150, height: 42)
                    }
                    .buttonStyle(.borderedProminent).tint(red).disabled(model.running)
                    Button(action: model.stop) {
                        Label("停止", systemImage: "stop.fill")
                            .frame(width: 110, height: 42)
                    }
                    .buttonStyle(.bordered).disabled(!model.running)
                    Spacer()
                    Text("Schedru 每 5 秒刷新  ·  WebReg 每 1 分钟刷新")
                        .font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
                }
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                    Text("开放时会自动向 WebReg 提交对应课程。请确认 Safari 中已登录正确账号，且监听课程无误。")
                        .font(.system(size: 13)).foregroundStyle(.primary)
                }
                .padding(14).frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))

                Text("当前课程与运行日志").font(.system(size: 17, weight: .bold))
                TextEditor(text: $model.output)
                    .font(.system(size: 12, design: .monospaced))
                    .scrollContentBackground(.hidden)
                    .padding(8)
                    .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.gray.opacity(0.2)))
            }
            .padding(24)
            Spacer(minLength: 0)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }
}
