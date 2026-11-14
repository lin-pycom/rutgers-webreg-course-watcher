# Rutgers 选课监听程序（动态版）

这是一个独立副本，原来的 `watcher.py` 不会被修改。动态版会读取 Schedru 仪表板 **Spring 2027 → Active Snipes** 中当前显示的课程 index，不再把五个课程号写死在程序里。

## 工作方式

- 启动时逐门显示 Active Snipes 中的课程名称、课程代码/section、index 和当前状态；课程状态变化时也会显示对应课程名称。
- 之后每 5 秒刷新并检查一次 Schedru 页面。
- 如果 Active Snipes 增加或减少课程，程序会更新正在监听的 index。
- 新增课程会显示课程名称；如果网页暂时没能读出名称，会明确显示“课程名称暂未识别”，但仍会列出 index。
- 发现课程明确显示开放，或课程从 `CLOSED` 变成 Schedru 的 `[EMAILED]` 开放通知状态后，程序会再次确认状态，然后只把那一个 index 填进 WebReg 并点击提交。
- WebReg 页面每 60 秒刷新一次以保持会话；如果需要选择学期，程序会选择 Spring 2027 并继续。
- 提交一次后，程序会显示 WebReg 的结果并退出。

## 启动前准备

1. 在 Safari 中登录 Schedru，打开仪表板并选择 Spring 2027。
2. 在另一个 Safari 标签页登录 Rutgers WebReg，打开 Spring 2027 的 Manage Registration 页面。
3. Safari 的“Allow JavaScript from Apple Events”需要已开启。程序只使用这两个已打开的 Safari 标签页，不会代替你输入密码或重新登录。
4. 确认 Schedru 的 Active Snipes 卡片就是你希望自动提交的课程。启动后程序会监控页面上实际列出的 active 课程。

## 运行中的按键

- 输入 `Q` 并回车：停止监听。
- 输入 `T` 并回车：**立即真实提交**当前 Active Snipes 列表按数字排序后的第一门课，只提交一个 index。若该课程此时可注册，WebReg 可能会实际把它加入你的课表；这不是模拟测试。

自动触发时也会真实点击 WebReg 的提交按钮。请只在你已确认课程列表、学期和注册意图后运行。

## 文件

- `watcher_dynamic.py`：动态版程序。
- `README_中文.md`：本说明。
