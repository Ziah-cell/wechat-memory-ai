# 普通个人微信长期记忆 AI · 正常窗口方案 v0.1.23

微信保持正常打开，允许其他应用在前台或遮挡微信；程序不置顶、不恢复窗口、不抢输入焦点。2026-10-12 已实际删除最小化读取与内部采集研究代码，不再支持最小化路线。

长期记忆、有限自然偏好、会话隔离、模型适配、去重和暂停/停止核心继续保留。**真实微信自动回复尚未接通**，默认 fake、网络关闭、real_send=false。普通窗口的非前台收发必须实测，不能由离线测试推定。

本次实机发现微信未向 UIA 暴露独立窗口标识，读取在身份发现阶段停止，未读取正文或捕获像素；非前台/遮挡读取和不抢焦点发送仍待验证。详见[当前状态](docs/STATUS.md)、[窗口实测](docs/OPEN_WINDOW_VALIDATION.md)。

在本目录运行（Python 3.11+）：

```powershell
.\scripts\windows.ps1 -Action test
.\scripts\windows.ps1 -Action offline-check
```

离线演练使用临时数据与假模型。个人配置、.env 和真实数据不会被清理覆盖。[自然偏好](docs/NATURAL_PREFERENCES.md)、[DeepSeek 适配](docs/DEEPSEEK.md)仍可复用。

只读监听只支持 `visual`，要求唯一已授权独立好友窗口正常打开。开始/停止命令和失败边界见[常驻只读监听](docs/CONTINUOUS_LISTENER.md)。监听只计数，不调用模型、写记忆或发送。

[清理记录](docs/evidence/558-window-open-cleanup.json)记录实际删除；[执行计划](docs/WINDOW_OPEN_PLAN.md)记录下一步。docs/history 与标注历史的研究报告仅保留事实，里面的旧命令、继续研究指令和源码哈希均不再适用于当前工作副本。Git 历史未重写。
