# 普通个人微信长期记忆 AI Implementation Plan

## v0.1.4 免费 OCR 可行性阶段

- [x] 新增只生成内存虚构气泡的 ocr-check，Windows 自带 API、独立超时与脱敏输出，不接入真实聊天。
- [x] 检查浅色/深色/大字号的重复中文、字母数字与行数，保留实际 recognition_mismatch，不做字符猜测。
- [x] 测试先行，11 项新增和完整 108 项回归、临时安装后检查、独立审查。
- [x] 更新状态与免费路线，实际局限见 [OCR_CHECK.md](OCR_CHECK.md)。

稳定身份、真实消息监听与发送仍未完成；本轮 MSAA 只读检查被自动审批拒绝，未执行、未获得结果。

> v0.1.0 历史实施计划。Windows v0.1.1 续开发见 [Windows 实测与修复计划](superpowers/plans/2026-10-01-windows-validation.md)，当前 v0.1.2 免费只读准备阶段见下节，结果以 STATUS.md / TEST_RESULTS.md 为准。

## v0.1.2 免费只读准备阶段

后续实机检查已执行：用户确认登录/测试窗口准备好，现有 4.1.15.50 两个可见窗口各只暴露 8 个基础控件，没有取得稳定身份/消息 UI 证据，真实监听继续阻塞。过程见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。

独立开发阶段安排：当时用户将第二个号登录放到后续，v0.1.3 先完成不依赖真实 UI 的回调传输组件与离线演练：

- [x] 测试先行，实现有界队列、构造线程消费、代次撤销、溢出/关闭/消费失败停止。
- [x] 内置虚构事件通过工作线程入队，创建队列的线程使用现有 Engine/FakeModel/临时 SQLite。
- [x] 新增 offline-check 命令，不读取个人配置/凭据，不探测真实微信，输出脱敏检查结果。
- [x] 完整回归 97/97、独立审查、临时安装后演练通过，按阶段提交同一仓库。

队列不构成真实监听或稳定身份验证，完整契约见 [OFFLINE_CHECK.md](OFFLINE_CHECK.md)。

用户已授权直接推进、按阶段测试并 commit/push 到同一仓库。范围是本人正常登录下的免费 UIA 路线，真实发送禁用；不重复实现核心。

- [x] 核对干净的 implementation 分支、07f4ccb 基线、绑定远程和本机 4.1.15.13 / 未运行状态。
- [x] 核查 pywechat127 1.9.8 wheel/sdist 依赖/许可/哈希；记录与上游当前源码差异，不安装/导入。
- [x] 先写失败测试，实现独立 Windows 原生 UIA 结构诊断：进程路径限定、属性白名单、节点/深度/时间上限、不读取正文或操作 UI。
- [x] 虚构 Windows 窗口与实际子进程回归；完整 84/84；临时隔离构建安装；独立只读审查。
- [x] 更新状态、实机矩阵和脱敏证据；交付方式仅 GitHub 阶段更新。
- [ ] 本人登录受控第二个号并确认唯一测试好友后，读取真实 UI 结构并验证稳定身份。
- [ ] 身份与边界条件满足后，实现只读监听/dry-run；回调排队、SQLite 单处理线程，实测历史/相同文本/重启/自身/重名/窗口切换。

设计与当前限制见 [READ_ONLY_PROBE.md](READ_ONLY_PROBE.md)。未满足实机前提时不虚构 peer/message ID 或把结构探针接入运行时。

## v0.1.0 历史计划正文

> **For agentic workers:** 使用 superpowers:executing-plans 在本会话逐项实现。用户已要求直接开发和运行测试；不再增加需求批准环节。

**Goal:** 交付可离线运行、有记忆和发送保护的模拟聊天核心与 Windows 交接包。

**Architecture:** 串行编排器连接可替换适配器、模型和本地 SQLite。内容备份与不可回滚的安全账本分离。

**Tech Stack:** Python >=3.11，SQLite，unittest，TOML；无第三方运行依赖。

**Spec:** CODEX_TASK.md、docs/DESIGN.md 与本轮范围。

## Global Constraints

- 真实微信发送关闭，本版不可启用；所有验收均明确 mock / HTTP 本地测试。
- 不要求在聊天提交密码/API Key；不装微信、不读取私人目录。
- 单联系人白名单、并发数 1、不自动重试、不使用运行时工具。
- 使用稳定消息 ID，不用正文散列合并合法的相同文本。
- 遗忘清理历史和摘要；恢复保留最新账本；日志不含正文/密钥。

## Review Focus

- 恢复旧备份之后，旧偏好和已删除内容不得从摘要复活（任务 2）。
- 用户输入伪装指令时，白名单和秘密不进入模型权限范围（任务 3）。
- 发送前窗口切换、发送结果未知与进程崩溃不得触发自动重发（任务 3）。
- 配置类型错误、非有限预算、HTTP 重定向不得静默降级（任务 1、3）。
- 真正的子进程锁竞争、暂停和停止应可在无 GUI 环境验证（任务 4）。

## Task 1: 配置与契约

Files: config.example.toml、.env.example、pyproject.toml、src/wechat_memory/config.py、tests/test_config.py。

Interfaces: `load_config(path, environ=None) -> Config`；不可变 Config；明确拒绝错误字段与真实发送。

- [x] 测试默认离线、白名单必填、范围和类型、网络密钥、秘密不在 repr。
- [x] 执行测试，记录缺少实现时预期失败。
- [x] 实现配置校验与本机 .env 凭据读取。
- [x] 全套测试通过并提交。

## Task 2: 持久化与记忆

Files: store.py、memory.py、backup.py、tests/test_memory.py。

Interfaces: `Store(data_dir)`；`MemoryService.handle(session, text, source) -> str | None`；`backup_store(store, path)`、`restore_backup(path, data_dir, guard_path)`。

- [x] 测试重启、覆盖、临时状态、敏感信息、检索隔离、确认清空、遗忘与旧备份恢复。
- [x] 运行预期失败，再实现独立账本/记忆/摘要/恢复。
- [x] 全套通过，记录取舍并提交。

## Task 3: 对话与发送状态机

Files: adapters.py、models.py、engine.py、audit.py、tests/test_engine.py、tests/test_models.py。

Interfaces: `Engine.process(Event) -> Result`，`Model.complete(messages, cancel_check=None) -> str`，`Adapter.identity()` / `send(expected, text)`。

- [x] 测试中文、多行、去重、顺序、自身、历史、非白名单、重名、窗口切换、断线、未知发送。
- [x] 测试模型故障、空回复、预算/超时、网络禁用、上下文边界、注入内容无权扩大能力。
- [x] 运行失败，实现对应行为；全套验证并提交。

## Task 4: 运行控制与交付

Files: runtime.py、cli.py、scripts/*、tests/test_runtime.py、README.md、docs/STATUS.md、docs/COMPATIBILITY.md、docs/ACCEPTANCE.md。

- [x] 子进程测试 CLI、锁冲突、pause/resume/stop、备份恢复、配置诊断。
- [x] 运行失败，实现跨平台控制；核验 Windows 脚本的静态内容，明确未执行。
- [x] 执行完整测试、编译、安装/模拟演示、压缩包解压运行。
- [x] 进行独立代码审查，修复重要问题；生成测试报告、状态文档与完整压缩包。
