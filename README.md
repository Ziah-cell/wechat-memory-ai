# 普通个人微信长期记忆 AI

当前 v0.1.23：已取消并删除最小化读取与内部采集研究程序。微信采用正常打开、可非前台/遮挡、不抢焦点的方案；真实自动回复尚未接通。

长期记忆、偏好、会话隔离、模型适配和暂停/停止核心保留。当前实机 UIA 窗口标识不可用，遮挡收发尚待验证。

```powershell
cd wechat-memory-ai
.\scripts\windows.ps1 -Action test
.\scripts\windows.ps1 -Action offline-check
```

[使用说明](wechat-memory-ai/README.md) · [当前状态](wechat-memory-ai/docs/STATUS.md) · [清理与窗口计划](wechat-memory-ai/docs/WINDOW_OPEN_PLAN.md) · [测试结果](wechat-memory-ai/docs/TEST_RESULTS.md)

个人配置、密钥、聊天/记忆数据不提交。默认 fake、网络关闭、真实发送禁用。
