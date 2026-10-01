# 普通个人微信长期记忆 AI Implementation Plan

## v0.1.7 实机连续监听与 UIA 能力诊断

用户要求继续下一阶段。首次使用 v0.1.6 实机监听：25 次接受快照、2 个新增行/1 个新增文本后停止，证据 [84](evidence/84-live-continuity-monitor.txt)。随后原生读取连续 3 次确认两条测试文字可见且快照稳定，但旧报告没有原因字段，不能推断该次停止原因或声称连续监听通过。

本轮为已有读取流程的有界诊断改动：停止原因使用固定白名单，记录已接受顶部移除次数及已见 token 数；不改变连续性/容量规则、不接入发送或模型。用户进一步授权自主推进到自动回复启用前，继续 TDD，不重复需求或权限批准。

- [x] 先补失败测试：原因区分、首次停止原因保留、非白名单异常脱敏、CLI 原因传播、中断和成功计数原子性。
- [x] `ReadSession.stop(reason)` 维护终止状态；`report()` 增加 `stop_reason/front_evictions/seen_tokens`；CLI 保留已产生的具体原因。
- [x] 原生程序输出固定阶段错误码、Python 区分超时；新增布局与 UIA 能力检查，不读取消息 Name，严格验证和脱敏输出。
- [x] 有界只读实测：第一条测试来信接受，第二条 RuntimeId 复用导致停止（92）。7文本行全宽、无子控件；9行中有7行共用同一非空 AutomationId，没有发送方/滚动能力证据（95/101）。保留早期失败及中断，不宣称连续监听通过。
- [x] 14 项新增回归，33 项定向通过；同时修复极大整数几何输入导致未脱敏 OverflowError 的边界。
- [x] 完整150项回归通过，独立审查无待修复代码发现，修正汇总计数的文档推断；版本更新为0.1.7，按授权准备同一 implementation 分支交付。

常规 commit/push 与远端 SHA 核验结果以最终交付回执为准。

自动回复前仍需可靠的新消息来源和发送方证据。现有 UIA-only 接口不满足；不得用共享 ID、正文哈希或默认将未知视为来信的方法绕过。像素/头像方案需要另行实现并验证遮挡、裁切、主题、长消息和历史滚动反例，当前未实现，不把上游启发式当成已验证能力。

## v0.1.6 顶部移除后的监听连续性修复

本阶段接续 v0.1.5 和已完成的真实固定文本收发验收。保留原始失败证据：旧监听器在 8 行变 9 行、保留末尾 6 行并追加 3 行时停止，没有返回新增观察。固定回复仅通过 Computer Use 发送一次且用户确认收到，授权已用完；无需重登或重做收发。

- [x] 保留 6 项新增回归和 [79](evidence/79-live-overlap-red.txt)；接续后复现 19 项、6 errors（一个测试的两个子例），均因合法顶部移除尚不支持。
- [x] 完整前缀追加继续有效；顶部移除只接受旧连续后缀与新前缀的 token 和内容摘要完全一致，至少两个锚点且有追加行。
- [x] 只有移除、单锚点、无重叠、内部移除/重排/内容变化、绑定变化均停止；记录本会话已见 token，重现或超过 4096 个时整批停止，不返回部分结果。
- [x] 19 项定向及完整 136 项回归通过；按 requesting-code-review 独立审查，无待修复发现。最终 Windows 入口复验与审查见 [82](evidence/82-live-overlap-final-suite.txt)、[83](evidence/83-live-overlap-review.json)。
- [x] 更新版本、状态与证据，准备同一仓库阶段交付；不启用模型、自动回复、记忆或项目发送适配器，不生成修订 ZIP。

交付按已有授权常规 commit/push 到 implementation，并核对远端 SHA；实际提交与上传结果以最终交付回执为准。

## v0.1.5 实际窗口只读连接（历史记录）

用户要求继续直到接入微信，并已本人重新登录。Computer Use 看到独立私聊窗口的 `ChatSingleWindowwxid_…` 标识、输入框和消息列表；新的独立原生读取程序也已取得该窗口的 8 个列表项，其中 5 个为文本。这改变了此前控件不可读的实测状态，但还不能证明发送方或跨重启消息 ID。

- [x] 以当前真实结构为依据，实现只读原生提供器：完整客户端路径限定、唯一独立私聊窗口、有界树/列表、子进程超时，不含输入/发送操作。
- [x] 实现会话内快照连续性：首次只建立基线，相同文字的新条目不合并；窗口/进程/列表变化，条目重建/改动/移除/重排时停止。
- [x] RuntimeId 只作当前 UI 实例的比较令牌；本地观察编号不是微信消息 ID，未知发送方不接入 Engine 或模型。
- [x] 新增独立 listen-wechat 入口；默认仅输出计数，核心仍拒绝真实发送。
- [x] 后续已看到两条相同左侧来信并由原生读取器读到两个文本项；旧监听器停止而无新增观察，已在 v0.1.6 修复，修复后的真实连续监听仍待验收。
- [x] 原生编译/双 PowerShell 入口测试、完整回归 130/130、临时构建安装与独立审查（发现已修复并关闭）。

## 独立免费 OCR 候选阶段（核心仍 v0.1.4）

- [x] 补测 Windows OCR 黑白化、缩放与可用语言；字母数字问题未消除，不修改原始失败判断。
- [x] 核验 RapidOCR 来源/模型哈希，在项目隔离环境安装并记录固定依赖；不改系统 Python 或核心依赖。
- [x] 保留 5 张固定虚构图和源码树实验脚本；超时、模型/图片校验、低分结果保留与脱敏报告。
- [x] 增加真实下划线反例，保留 review_required，不把过滤后匹配说成可自动处理。
- [x] 9 项新增测试，完整 117 项通过；独立审查两项发现修复并复验关闭，更新状态和证据。

结果见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。真实身份、新消息来源与去重仍未验证，不重复登录或用昵称/OCR 文本替代稳定身份。

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
