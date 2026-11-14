# Rutgers WebReg Course Watcher / Rutgers WebReg 选课助手

English | [简体中文](#简体中文)

A macOS desktop helper that monitors active course alerts and submits one course index through an already signed-in Safari session.

> **Important:** An opening causes automatic form filling and submission to WebReg, which can change the user's actual registration. Confirm the watched courses before starting. This is an independent project, not affiliated with Rutgers University or Schedru.

## Features

- Reads indexes from the current **Active Snipes** list; no fixed course list in source.
- Refreshes/checks course alerts every 5 seconds; refreshes WebReg every 60 seconds.
- Shows course name, course/section code, index, and status.
- Submits only the index associated with an opening, then shows WebReg's response.
- Native macOS window with Start/Stop buttons and live logs.

## Requirements and use

- macOS 13+; package contains Apple Silicon and Intel builds.
- Python 3.9+ and Safari with both course alerts and Rutgers WebReg signed in.
- Enable Safari **Develop → Allow JavaScript from Apple Events**. macOS may ask permission for the app to control Safari.
- Extract `release/WebRegWatcher-macOS.zip`, then open `WebRegWatcher.app`. If blocked, Control-click the app in Finder and choose **Open**. The app is not Developer ID signed or notarized, so macOS may show a security warning.
- Sign in to your own Safari sessions, configure your courses, and click **Start Monitoring**. The app submits automatically when an opening is detected; **Stop** ends monitoring.

The app stores no credentials. Follow Rutgers registration rules; no seat or successful submission is guaranteed.

## Source and screenshots

- `src/Launcher.swift` - desktop window and process launcher.
- `src/watcher_dynamic.py` - dynamic watcher and WebReg automation.
- `docs/USER_GUIDE_BILINGUAL.pdf` - Chinese/English manual.

![Safari automation permission](docs/images/safari-automation-setting.png)

![WebReg assistant window](docs/images/webreg-assistant-window.png)

---

## 简体中文

这是一个 macOS 桌面助手，通过已登录的 Safari 会话监听课程空位提醒，并向 Rutgers WebReg 提交对应课程。

> **重要：** 检测到开放时，程序会自动填写并提交 WebReg，可能改变真实课表。启动前请确认监听课程。本项目为独立项目，与 Rutgers University 或 Schedru 无隶属关系。

### 功能

- 自动读取当前 **Active Snipes** 列表，不固定写入课程 index。
- 每 5 秒刷新并检查课程提醒页面；每 60 秒刷新 WebReg。
- 显示课程名称、课程/section 代码、index 和状态。
- 只提交开放的对应课程，并显示 WebReg 返回结果。
- 原生 macOS 窗口，提供开始/停止按钮和实时日志。

### 要求与使用

- macOS 13 或更新版本；安装包包含 Apple 芯片和 Intel 版本。
- 需要 Python 3.9+；Safari 中登录课程提醒页面和 Rutgers WebReg。
- Safari 开启 **Develop → Allow JavaScript from Apple Events**；macOS 可能询问是否允许应用控制 Safari。
- 解压 `release/WebRegWatcher-macOS.zip` 并打开 `WebRegWatcher.app`。若系统拦截，在 Finder 中按住 Control 点按应用并选“打开”。应用没有 Developer ID 签名或公证，因此可能出现安全提示。
- 登录自己的 Safari 会话并设置监听课程，点击“开始监听”。开放时会自动提交；点击“停止”结束监听。

应用不保存账号密码。请遵守 Rutgers 注册规则；不保证名额或提交结果。

### 源码与截图

- `src/Launcher.swift` - macOS 窗口和启动器。
- `src/watcher_dynamic.py` - 动态监听及 WebReg 自动操作。
- `docs/USER_GUIDE_BILINGUAL.pdf` - 中英文双语使用手册。

![Safari 自动化权限设置](docs/images/safari-automation-setting.png)

![WebReg 助手窗口](docs/images/webreg-assistant-window.png)
