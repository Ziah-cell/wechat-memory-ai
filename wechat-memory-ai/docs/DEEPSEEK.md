# DeepSeek 非思考模式接入与评估

v0.1.15已完成隔离虚构对话的8次真实DeepSeek API技术调用，但后续质量检查发现模型编造偏好及删除断言，不能判为聊天质量通过。本轮测试已结束，不再调用API。微信消息源未接入模型，自动回复和实际聊天记忆写入保持关闭。

v0.1.16另加入有限日常偏好的本地提取与命名管理，见[NATURAL_PREFERENCES.md](NATURAL_PREFERENCES.md)。这次更新只用虚构数据和假模型验证，没有新增真实API请求，也不代表此前质量失败已经全面解决。

## 已准备的配置

仓库中的[config.deepseek.example.toml](../config.deepseek.example.toml)预填官方端点与`deepseek-flash`，但仍为`provider="fake"`、`allow_network=false`；默认`config.example.toml`和主`config.toml`同样保持fake、关闭网络。本机另有被Git忽略的`config.local.deepseek.toml`评估配置，已启用DeepSeek网络请求，仍限定`adapter="mock"`、`dry_run=true`、`real_send=false`。

真实模型需要本机同时满足三个条件：`provider="deepseek"`、`allow_network=true`，以及环境变量或同目录`.env`中的`WECHAT_AI_API_KEY`。用户已在本机填写密钥；`.env`被Git忽略，密钥内容不输出到工具结果、TOML、日志、聊天或Git。

`dry_run=true`只禁止发送，不禁止模型请求、额度消耗或本地模拟记忆。它不能代替网络开关。当前代码只允许mock适配器，`real_send=true`仍明确拒绝；填写密钥不等于启用微信自动回复。

## 已完成的隔离评估

[204](evidence/204-live-model-synthetic-evaluation.json)的6次虚构对话和[206](evidence/206-live-model-style-follow-up.json)的2次复测均返回完整文本，完整模型请求耗时为0.697–2.390秒。这是8次小样本，不是微信端到端延迟或稳定速度承诺。测试使用临时Store，虚构记忆数据已清理，没有读取微信、写入实际聊天记忆或发送消息。

[205](evidence/205-live-model-style-review.json)指出首轮回复对内部记忆过程解释过多；提示调整后的206仍在记录为空时编造饮品偏好，并声称该虚构偏好已删除。因此技术成功不等于质量通过，提示词不足以阻止此类猜测。现已对有限饮品回忆问句增加结构化查询，12项定向测试及[213独立审查](evidence/213-memory-recall-review.json)通过；这是局部离线修复，未再次调用真实模型验证，也不代表其他主题回忆已可靠。

## 请求和响应契约

DeepSeek配置只接受两个明确的官方HTTPS端点：

- `https://api.deepseek.com/chat/completions`
- `https://api.deepseek.com/v1/chat/completions`

请求发送`model`、`messages`、`stream=false`、`thinking={"type":"disabled"}`；现有`max_completion_tokens`配置映射为DeepSeek的`max_tokens`。不发送`reasoning_effort`、`store`、工具或其他通用客户端字段。原`chat_completions`模式保持既有格式，不能把它与专用非思考适配混为一谈。

响应须正常停止且包含非空文字。被服务端截断、超过本地字符上限的文本不会裁成半句话交付，而是返回固定`truncated`错误。其他异常结束、非空推理内容或工具调用按格式错误拒绝，不将这些字段暴露到回复或错误日志。

沿用原客户端的整体超时、可取消子进程、1MiB响应上限、禁止重定向与不自动重试。请求仍可能遇到服务端排队；单元测试不证明云服务延迟。输出token上限只约束输出，本地字符预算和金额估算不是实际计费；省略`store`不构成服务商不保留数据的承诺。

## 聊天与记忆范围

系统提示默认日常一到三句、自然口语，复杂问题按需展开。有限饮品回忆查询只读取当前会话已保存的明确偏好，未知或多条记录不交给模型猜测；状态回答只描述当前记录，不推断删除历史。已有明确记忆、纠正和遗忘继续生效；v0.1.16已支持三个主题的有限日常表达提取，通用提取、一般事实回忆与自然度验收仍待完成。支持范围见[CHAT_EXPERIENCE.md](CHAT_EXPERIENCE.md)。

模型将来用于真实聊天时，本轮正文及选中的上下文会发送给服务商；本地持久保存记忆不等于所有生成均在本地完成。

官方契约核对日期2026-10-03：[请求参数与响应](https://api-docs.deepseek.com/api/create-chat-completion/)、[非思考开关](https://api-docs.deepseek.com/guides/thinking_mode/)、[兼容端点示例](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy/)、[连接保活](https://api-docs.deepseek.com/quick_start/rate_limit/)。`deepseek-flash`是服务商模型别名，不保证永远指向同一版本。
