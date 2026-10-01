# 普通个人微信长期记忆 AI

采用免费接入路线，按开发阶段直接更新本 Git 仓库。当前核心版本 **v0.1.4**：已有持久记忆、遗忘、备份恢复、单实例、运行控制与独立诊断。真实微信 UIA 检查未取得身份/消息控件，普通个人微信收发尚未接通。

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
| Windows 离线核心、记忆与运行控制 | 已完成；当前完整回归 117 项通过 |
| 免费微信接入候选核验 | 已做登录后的 UIA 检查；稳定身份与消息来源仍未取得 |
| 免费本地 OCR 候选 | 独立环境实测改善字符识别，但仍有误检/漏字，保持需核查 |
| 唯一好友只读监听与 dry-run | 尚未实现 |
| 固定文本真实发送、模型组合、长期运行 | 尚未验证 |

- [当前状态](wechat-memory-ai/docs/STATUS.md)
- [测试证据](wechat-memory-ai/docs/TEST_RESULTS.md)
- [完整使用说明](wechat-memory-ai/README.md)
- [免费接入路线](wechat-memory-ai/docs/FREE_ROUTE.md)
- [OCR 候选实测](wechat-memory-ai/docs/OCR_CANDIDATE.md)
- [后续阶段更新约定](wechat-memory-ai/docs/REPOSITORY_WORKFLOW.md)

本仓库保存源码、测试、示例配置和开发记录。个人配置、API Key、聊天数据库、日志、备份与旧交付压缩包保留在本机。免费接入库与模型费用是两件事；当前假模型无需付费，真实模型尚未选定。
