# 正常窗口的常驻只读监听

v0.1.23 只保留普通窗口 `visual` 联合读取。微信必须保持正常打开；可以不在最前、可以被其他应用遮挡，但相应实机能力仍按 [验证记录](OPEN_WINDOW_VALIDATION.md) 判定。程序不会激活、置顶、恢复窗口或输入文字。

仅打开唯一授权测试好友的独立聊天窗口，使用新状态目录启动：

```powershell
.\scripts\windows.ps1 -Action start-listener -ListenerData data/open-window-listener -ClientPath 'D:\软件\Weixin\Weixin.exe'
.\scripts\windows.ps1 -Action listener-status -ListenerData data/open-window-listener
.\scripts\windows.ps1 -Action stop-listener -ListenerData data/open-window-listener
```

`-ListenerReader` 只接受 `visual`；已删除的 background/selection 参数直接报错，不降级启动。Python 入口为 scripts/monitor-wechat.py，只有 `--reader visual`。本次没有启动常驻监听，旧 standby 状态保持 stopped；不要根据旧目录推断当前运行状态。

- 首个非空视口只建基线；不回放停机内容，不自动重绑/恢复。
- 最小化、窗口/列表变化、连续性丢失或超时即停止。`window_identity_unavailable` 表示可见微信根均无 UIA 标识，不能据此要求用户反复打开聊天。
- 明确 incoming/self 仍是视觉候选，不是已认证身份。unknown 不当来信；历史同步问题仍未解决。
- 监听只保存固定计数和耗时诊断；不加载个人配置/.env、不接模型、记忆或发送。状态 `reply_ready` 永远 false。
- `-KeepAwake` 仍是显式防自动待机请求，退出释放；不修改电源计划。它不能使锁屏、手动睡眠或最小化受到支持。

最小化专用统计与协议均已移除。此前的实验结果见 [历史归档](history/CONTINUOUS_LISTENER-before-window-open.md)，不能继续使用其运行命令。
