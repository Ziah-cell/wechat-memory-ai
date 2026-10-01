# 普通个人微信长期记忆 AI

采用免费接入路线，按开发阶段直接更新本 Git 仓库。当前版本 **v0.1.5**：已有持久记忆、遗忘、备份恢复、单实例和运行控制，并已用独立只读程序连接本机真实微信测试窗口、读取可见文本。新消息边界与发送方仍待实测，尚未接入模型或自动回复。

## 运行

```powershell
cd wechat-memory-ai
.\scripts\windows.ps1 -Action test
.\scripts\windows.ps1 -Action diagnose
.\scripts\windows.ps1 -Action run
```

Python 3.11+，核心和测试没有第三方依赖。脚本自动查找可用解释器，也支持 `-Python 'C:\实际目录\python.exe'`。默认 mock / fake / dry-run；真实发送无法启用。

## 阶段与进展

| 阶段 | 状态 |
|---|---|
| Windows 离线核心、记忆与运行控制 | 已完成；完整回归结果见测试证据 |
| 免费微信接入候选核验 | 当前本机测试窗口已可通过 UIA 读取 |
| 免费本地 OCR 候选 | 独立环境实测改善字符识别，但仍有误检/漏字，保持需核查 |
| 唯一好友独立只读连接 | 已实现并读取当前文本；新消息与方向待验收，未接入核心 |
| 固定文本真实发送、模型组合、长期运行 | 尚未验证 |

- [当前状态](wechat-memory-ai/docs/STATUS.md)
- [测试证据](wechat-memory-ai/docs/TEST_RESULTS.md)
- [完整使用说明](wechat-memory-ai/README.md)
- [免费接入路线](wechat-memory-ai/docs/FREE_ROUTE.md)
- [OCR 候选实测](wechat-memory-ai/docs/OCR_CANDIDATE.md)
- [真实微信只读连接](wechat-memory-ai/docs/LIVE_READ.md)
- [后续阶段更新约定](wechat-memory-ai/docs/REPOSITORY_WORKFLOW.md)

本仓库保存源码、测试、示例配置和开发记录。个人配置、API Key、聊天数据库、日志、备份与旧交付压缩包保留在本机。免费接入库与模型费用是两件事；当前假模型无需付费，真实模型尚未选定。
