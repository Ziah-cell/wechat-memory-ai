# 普通个人微信长期记忆 AI

采用免费微信接入路线，按开发阶段直接更新本 Git 仓库。当前版本 **v0.1.15**：DeepSeek已用虚构对话完成8次真实请求，模型完整请求耗时约0.7–2.4秒。测试发现模型在记忆为空时编造饮品偏好，并无依据声称已删除，现对有限的饮品回忆问句增加本地核对；一般聊天质量仍待验收。真实微信观察尚未接入模型、记忆或自动回复。

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
| 唯一好友独立只读连接 | 标记后双来信准入通过；新增绑定消息源，自身方向仅组件检查通过，未接入核心 |
| 固定文本真实发送 | 一次授权回复已通过，不重复发送 |
| 模型组合、长期运行与自动回复 | DeepSeek真实接口已连通；虚构对话暴露偏好猜测，有限问句已加本地核对；长期运行和自动回复未验证或启用 |

- [当前状态](wechat-memory-ai/docs/STATUS.md)
- [DeepSeek接入与评估](wechat-memory-ai/docs/DEEPSEEK.md)
- [测试证据](wechat-memory-ai/docs/TEST_RESULTS.md)
- [完整使用说明](wechat-memory-ai/README.md)
- [免费接入路线](wechat-memory-ai/docs/FREE_ROUTE.md)
- [OCR 候选实测](wechat-memory-ai/docs/OCR_CANDIDATE.md)
- [真实微信只读连接](wechat-memory-ai/docs/LIVE_READ.md)
- [后续阶段更新约定](wechat-memory-ai/docs/REPOSITORY_WORKFLOW.md)

本仓库保存源码、测试、示例配置和开发记录。个人配置、API Key、聊天数据库、日志、备份与旧交付压缩包保留在本机。免费接入库与模型费用是两件事；默认假模型无需付费；本机另有DeepSeek评估配置，真实API费用由服务商计费。
