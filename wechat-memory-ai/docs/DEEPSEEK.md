# DeepSeek 非思考模式接入准备

v0.1.14已增加专用请求适配与自然聊天提示。当前使用本地假HTTP服务验收，尚未调用真实DeepSeek API；真实速度、自然度和服务端兼容性仍待实际评估。微信消息源未接入模型，自动回复和实际聊天记忆写入保持关闭。

## 已准备的配置

仓库中的[config.deepseek.example.toml](../config.deepseek.example.toml)预填官方端点与`deepseek-flash`，但仍为`provider="fake"`、`allow_network=false`。默认`config.example.toml`和现有个人配置不被自动覆盖。草稿使用独立的模拟评估数据目录。

接入真实模型时，需要本机同时满足三个条件：`provider="deepseek"`、`allow_network=true`，以及环境变量或同目录`.env`中的`WECHAT_AI_API_KEY`。缺少任何必要条件都不能运行DeepSeek配置。`.env`已被Git忽略，密钥不写进TOML、日志或聊天；用户只需在自己的本机填写密钥，配置切换与后续测试可由开发任务继续完成。

`dry_run=true`只禁止发送，不禁止模型请求、额度消耗或本地模拟记忆。它不能代替网络开关。当前代码只允许mock适配器，`real_send=true`仍明确拒绝；填写密钥不等于启用微信自动回复。

## 请求和响应契约

DeepSeek配置只接受两个明确的官方HTTPS端点：

- `https://api.deepseek.com/chat/completions`
- `https://api.deepseek.com/v1/chat/completions`

请求发送`model`、`messages`、`stream=false`、`thinking={"type":"disabled"}`；现有`max_completion_tokens`配置映射为DeepSeek的`max_tokens`。不发送`reasoning_effort`、`store`、工具或其他通用客户端字段。原`chat_completions`模式保持既有格式，不能把它与专用非思考适配混为一谈。

响应须正常停止且包含非空文字。被服务端截断、超过本地字符上限的文本不会裁成半句话交付，而是返回固定`truncated`错误。其他异常结束、非空推理内容或工具调用按格式错误拒绝，不将这些字段暴露到回复或错误日志。

沿用原客户端的整体超时、可取消子进程、1MiB响应上限、禁止重定向与不自动重试。请求仍可能遇到服务端排队；单元测试不证明云服务延迟。输出token上限只约束输出，本地字符预算和金额估算不是实际计费；省略`store`不构成服务商不保留数据的承诺。

## 聊天与记忆范围

系统提示默认日常一到三句、自然口语，复杂问题按需展开；配置、当前明确表达要求和更新后的偏好可以调整默认习惯。已有明确记忆、纠正和遗忘继续生效；日常聊天自动提取长期偏好尚未实现。完整要求见[CHAT_EXPERIENCE.md](CHAT_EXPERIENCE.md)。

真实模型评估先使用虚构对话并禁止发送到微信。模型最终用于真实聊天时，本轮正文及选中的上下文会发送给服务商；本地持久保存记忆不等于所有生成均在本地完成。

官方契约核对日期2026-10-03：[请求参数与响应](https://api-docs.deepseek.com/api/create-chat-completion/)、[非思考开关](https://api-docs.deepseek.com/guides/thinking_mode/)、[兼容端点示例](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy/)、[连接保活](https://api-docs.deepseek.com/quick_start/rate_limit/)。`deepseek-flash`是服务商模型别名，不保证永远指向同一版本。
