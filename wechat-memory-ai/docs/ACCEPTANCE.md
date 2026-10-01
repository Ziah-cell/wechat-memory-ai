# 本轮验收

当前代码 v0.1.7，完整150项回归通过。真实4.1.15.50唯一测试私聊已可读；连续监听实测第一条来信接受、第二条因RuntimeId复用停止。布局/属性检查未提供足够的发送方与历史边界证据，**尚不能开始自动回复**。此前两条相同来信与一次授权固定回复验收仍有效，见 [78](evidence/78-live-exchange.json)。本轮未再发送，详见 [LIVE_READ.md](LIVE_READ.md) 与 [TEST_RESULTS.md](TEST_RESULTS.md)。

| 任务书要求 | 实现/实际结果 | 证据 |
|---|---|---|
| 独立项目、完整任务书、计划/状态 | 已创建，原任务书保留 | CODEX_TASK.md、AGENTS.md、DESIGN/PLAN/STATUS |
| 真实发送默认关闭 | 本版直接拒绝 real_send=true 或真实 adapter | test_config、diagnose |
| 模拟消息与中文/多行 | 已实现控制台和 JSONL | test_engine、test_runtime |
| 单联系人、稳定会话与隔离 | mock ID 绑定会话；不使用昵称授权 | test_engine、test_memory |
| 历史/自身/群聊/非白名单过滤 | 已实现且不调用模型 | test_engine |
| 持久化去重、重启、不盲重发 | guard 保存状态；处理未完成时终止或待核查 | test_engine |
| 连发顺序、并发上限 | FIFO 模拟队列、串行处理、max_concurrency=1 | test_engine、test_runtime |
| 回调工作线程与单线程 SQLite | 有界队列，只有创建线程可消费；默认 128 条 | test_callback_inbox |
| 订阅撤销/溢出/关闭 | 旧回调失效、积压清空、不自动补发；已交出事件不能撤回 | test_callback_inbox；真实来源未接入 |
| 无需登录的一键演练 | offline-check 使用内置假消息/假模型/临时 SQLite，不读取个人配置 | evidence/42、43、44 |
| 登录后的正常 UIA 读取 | 当前唯一独立测试私聊已可读取列表/文本；此前仅基础控件状态已变化 | evidence/69、73、78 |
| 真实普通个人号固定文本收发 | 两条相同来信、一次 Computer Use 固定回复，用户确认收到；该次发送授权已用完 | evidence/78 |
| 顶部旧行移出后的连续读取 | 第一次实机顶部移除接受；第二条因已见token复用停止，未通过 | test_live_read、evidence/92 |
| 停止原因与只读能力检查 | 固定原因、计数原子性、布局/属性存在性检查；不输出正文或属性值 | test_live_read、evidence/95、100、101、102 |
| 假模型与可替换接口 | 已实现，真实 HTTP 可选并默认禁止 | models.py、test_models |
| 上下文窗口与摘要 | 有界历史/摘录和有限相关记忆 | test_engine、test_memory |
| 长期偏好、事件、来源与时间 | 显式指令写入；普通临时对话不固化 | test_memory |
| 查看、纠正、删除、确认清空 | 已实现；删除/纠正清理旧历史和摘要 | test_memory |
| 备份恢复遵守遗忘 | 独立 guard；恢复前完整性/结构校验并重放 | test_memory、test_review_regressions |
| 模型故障、预算、超时 | 无自动重试，费用预留持久化，总时限与可取消进程 | test_models、test_engine、test_review_regressions |
| 窗口切换/身份不明 | 在 mock 中拒绝并暂停 | test_engine；实机未验证 |
| 启停与单实例 | 当前平台子进程实测通过 | test_runtime |
| 脱敏日志、注入不增权 | 仅固定元数据；模型没有执行工具/秘密/配置能力 | test_engine |
| Windows 脚本和后续说明 | v0.1.1 已在 PowerShell 5.1/7 运行并验证配置保护/退出码 | test_windows_scripts、evidence/22-windows-green.txt |
| 自动安装/登录/自启动/自动发信 | 本轮未执行；此前一次人工授权固定回复不构成自动发送能力 | STATUS、evidence/78 |

Windows 离线复验已完成：完整测试与独立的 9 步记忆/重启/遗忘/旧备份恢复验收见 TEST_RESULTS.md 和 evidence/23-windows-acceptance.json。实机矩阵见 WINDOWS_NEXT.md，未完成的连续监听、身份/历史边界等验收不能用 mock 结果打勾。
