# 普通个人微信长期记忆 AI · 后台读取时序诊断 v0.1.20

普通聊天窗口的最小化文本读取无需保持多选；常驻进程支持启动、状态和停止。v0.1.20在固定阶段与耗时诊断上额外保留一份最慢读取详情，避免后续快读覆盖慢读证据。8秒预算与既有停止/重启保护不变。旧超时根因仍未确定，不能宣称长期稳定；全部收发方向为unknown，**自动回复未开启**。运行方式见[常驻监听说明](docs/CONTINUOUS_LISTENER.md)，诊断与恢复边界见[时序说明](docs/READER_TIMING.md)。

新增饮品、咖啡加糖和回复长度三个主题的有限日常表达识别，例如“我喝咖啡不加糖”，可本地保存后继续正常生成一次聊天回复。明确命名的纠正、遗忘和查询在本地完成，未知/歧义不猜；支持范围与例子见[日常偏好说明](docs/NATURAL_PREFERENCES.md)。当前仍为模拟聊天核心，真实微信自动回复保持关闭。

DeepSeek先前8次虚构请求的完整耗时0.697–2.390秒，仅为小样本；其中发现编造偏好及删除状态断言，一般质量未通过。新密钥另用虚构短输入完成一次连通检查；不代表质量已通过。默认配置和[配置草稿](config.deepseek.example.toml)仍fake/网络关闭，本机另有被Git忽略的模型评估配置；详见[DEEPSEEK.md](docs/DEEPSEEK.md)及[聊天范围](docs/CHAT_EXPERIENCE.md)。

核心聊天入口仍是**控制台模拟器**。随机标记之后两条相同真实来信的只读准入已通过。v0.1.13把这条路径封装为必须指定窗口实例的只读消息源；到期、关闭或失败后失效，发送始终拒绝。已绑定联合读取只在快照前后变化时有限重取，保持原基线。该阶段选定237项回归通过。224已通过同一指定来源中新自身过滤、后来信交付与关闭失效的受控实测。**尚不能开始自动回复**；身份/历史及发送桥接仍待完成。详见 [测试结果](docs/TEST_RESULTS.md)、[只读消息源](docs/LIVE_SOURCE.md) 和 [候选模式说明](docs/READ_CANDIDATES.md)。

此前两条相同来信与一次经授权的固定回复验收仍有效，回复由 Computer Use 发送且用户确认收到。本轮没有再次发送。最新结果与后续接入条件见 [docs/LIVE_READ.md](docs/LIVE_READ.md)。

只读连接运行：`.\scripts\windows.ps1 -Action listen-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe' -ListenSeconds 30`。只保留一个测试好友的独立聊天窗口，启动时建立基线，报告仅含计数。具体限制见 [docs/LIVE_READ.md](docs/LIVE_READ.md)。

v0.1.3 增加异步回调队列和一键离线演练。现在可运行 `.\scripts\windows.ps1 -Action offline-check`，用临时数据库和假模型验证回调、过滤、去重与停止边界；不读取个人配置或操作真实微信。详见 [docs/OFFLINE_CHECK.md](docs/OFFLINE_CHECK.md)。

此前实机检查曾只看到基础窗口控件，记录见 [docs/LIVE_UIA_CHECK.md](docs/LIVE_UIA_CHECK.md)。用户重新登录后，当前 4.1.15.50 已可读取测试窗口；原因尚未确定，不能据此保证其他账号或版本可用。

v0.1.4 增加 `.\scripts\windows.ps1 -Action ocr-check`：只用内存生成的虚构气泡检查 Windows 本地中文 OCR，不读取屏幕或真实聊天。本机引擎可运行，但浅色/大字号样例有识别误差，返回 `recognition_mismatch` / 退出码 3。完整 108 项程序测试通过，不代表 OCR 样例或真实微信接入通过。详见 [docs/OCR_CHECK.md](docs/OCR_CHECK.md)。

此前在独立 `.ocr-env` 实测免费 RapidOCR 候选，固定样例的中文和字母数字识别改善，但气泡边缘误检与真实符号漏字仍存在，结果为 `review_required` / 退出码 3。该阶段 117 项测试通过，详见 [docs/OCR_CANDIDATE.md](docs/OCR_CANDIDATE.md)。当前只读连接直接使用 UIA，不依赖 OCR。

离线模拟无需微信账号或模型密钥；真实模型评估使用用户已在本机填写的密钥。测试中的称呼、饮品和经历均为虚构，不代表用户真实偏好。

## 现在如何运行

需要 Python 3.11 或更新版本；核心与测试均没有第三方依赖。本版已在 Windows 11、Python 3.12.14、PowerShell 5.1/7 实测。不要因项目自动升降级微信。

Windows：从同一 GitHub 仓库更新后，进入 `wechat-memory-ai` 子目录，在该目录打开 PowerShell：

```powershell
.\scripts\windows.ps1 -Action test
.\scripts\windows.ps1 -Action diagnose
.\scripts\windows.ps1 -Action run
```

脚本只在默认 `config.toml` 不存在时复制示例，不覆盖已有配置。此处直接运行源码，不用先执行 pip install，也不需要管理员权限。

没有 `py` 启动器也可使用：脚本依次检查项目 `.venv`、PATH 中实际存在的 `py/python/python3`，最后检查本机 Codex 缓存运行时；跳过 WindowsApps 商店占位命令。也可指定 `-Python 'C:\你的目录\python.exe'` 或设置当前终端的 `WECHAT_MEMORY_PYTHON`。显式指定的解释器无效时直接报错，不悄悄改用另一环境。Codex 缓存路径可能随应用更新变化，长期运行可指定自己安装的 Python 3.11+。

Linux / macOS 的对应方式：

```bash
cp -n config.example.toml config.toml
python3 scripts/test.py
python3 scripts/run.py --config config.toml run
```

启动后每输入一行，代表一条新的模拟消息；回复以 JSON 输出，`status=dry_run` 表示仅预览。例如依次输入：

```text
记住：称呼我为小禾，回复尽量简短
你好
以后不要叫小禾，改叫阿禾
你记住了什么
/退出
```

重启后输入“你好”，假模型会使用保留的称呼，并明确标注“离线模拟”。假模型只验证流程，不能代表真实大模型的回答质量。测试结果与待办见 [docs/STATUS.md](docs/STATUS.md)。

多行文本、重复事件或身份字段测试可用 JSONL：

```powershell
# 将此路径替换为本机实际解释器；若已装 py，也可使用 py -3。
$Python = 'C:\你的目录\python.exe'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -Encoding UTF8 examples/demo.jsonl | & $Python -X utf8 scripts/run.py --config config.toml run --jsonl
```

JSON 中 `text` 可包含 `\n`。不填写时间时会被标记为“刚输入的模拟消息”，不能拿这个行为导入真实历史。重复的稳定 `id` 会在重启后继续被去重；正常文本模式每条输入分配不同 ID。

## 暂停、停止与状态

在另一个终端执行（配置必须指向同一数据目录）：

```powershell
.\scripts\windows.ps1 -Action status
.\scripts\windows.ps1 -Action pause
.\scripts\windows.ps1 -Action resume
.\scripts\windows.ps1 -Action stop
```

同一数据目录只允许一个运行或维护实例。暂停期间的新模拟输入会返回 `paused` 并丢弃，不自动积压补发；停止不使用 PID 杀进程。请求已进入真实模型 HTTP 调用时，主进程仍会轮询控制指令，并在发送前再次检查。HTTP 调用有总时限，由独立子进程执行；暂停、停止或到期会终止本地请求进程，轮询间隔不超过 50 毫秒（另有进程清理时间）。这不等于撤销服务商已经接收的计算或费用。

脚本支持 `run|test|status|pause|resume|stop|diagnose|backup|restore|review`，`scripts/diagnose-windows.ps1` 是诊断快捷入口。已在 Windows PowerShell 5.1 与 PowerShell 7 实测诊断、配置保护和错误码。若脚本执行受到本机策略限制，可直接用实际 Python 路径执行 `scripts/run.py`；项目不会修改系统策略或创建自启动任务。CLI 的管道输入/输出统一使用 UTF-8。

## 记忆操作

| 输入 | 行为 |
|---|---|
| `记住：称呼我为小禾，回复尽量简短` | 显式保存两条偏好 |
| `以后不要叫小禾，改叫阿禾` | 替换称呼，不同时保留两个互斥值 |
| `/记住 preference 兴趣=绘画` | 按指定键写入/覆盖偏好 |
| `/记住 event 考试=下周复习英语` | 写入事件与进度；同键新消息可更新 |
| `/记忆` 或 `你记住了什么` | 查看记忆 ID、类型和内容；每页 5 条 |
| `/记忆 2` | 下一页；展示内容最多 100 字 |
| `/纠正 ID=新的内容` | 修改该条，保留最初创建时间并更新来源 |
| `/忘记 ID` | 删除该条，并保守清理此前本会话历史和摘要 |
| `/清空记忆` | 取得会话绑定、60 秒有效的确认码 |
| `/确认清空 确认码` | 清空该会话记忆、历史与摘要 |

除[三个主题的有限完整表达](docs/NATURAL_PREFERENCES.md)可自动保存外，其他普通聊天不会自动成为长期记忆；例如“今天有些累，不想长聊”只进入会话上下文。上述明确命令仍可使用，未知命令格式会提示用法，未匹配的普通表达仍走聊天流程。这不是通用意图识别，也不能识别恰好符合支持句式的玩笑或反讽。

每条记忆保留 ID、类型、`certainty=explicit`、活动状态、来源事件引用及创建/更新时间。本版不生成待确认推测，也不将临时状态写成稳定人格。偏好优先检索；事件采用中文二字片段重合检索，最多 12 条且受字符预算限制。每个会话最多 100 条、单条值最多 500 字。

“称呼 / 回复长度 / 兴趣”等键应保持一致；自由文本键的同义词和逻辑冲突不会自动合并。程序的明确记忆管理指令不会交给模型执行，模型输出也不会被解析成命令。

## 配置、模型和费用

`config.example.toml` 包含唯一模拟联系人、角色语气、模型超时、输入/输出和上下文预算、调用与估算金额上限。路径相对于配置文件解析。未知字段和无效类型直接报错，不静默忽略。

默认 `provider="fake"`、`allow_network=false`。需要真实模型时，在自己电脑完成：

1. 核验服务商支持的接口、授权方式、模型名与费用；本版客户端只实现文本 Chat Completions。
2. 将 `.env.example` 复制为 `.env`，本机填写 `WECHAT_AI_API_KEY`，或设置同名进程环境变量（环境变量优先）。不要把密钥粘贴到聊天、命令示例或 Git。
3. 在 `config.toml` 填写完整 endpoint 和 model name，设 `provider="chat_completions"`、`allow_network=true`。保留 `real_send=false` 和 `dry_run=true`。
4. 先在模拟入口验证真实模型；此操作会向所填服务发送当前消息、必要记忆、有限历史/摘录，并可能产生费用。不会上传整个微信历史或电脑文件。

客户端使用 Bearer 凭据；非回环地址要求 HTTPS，拒绝 URL 内嵌凭据、查询参数和重定向。无自动重试。401/403、402/429、服务错误、网络断开、超时、空返回、非文本/畸形 JSON 均会终止本条处理，不自动重扣或重发。响应最大读取 1 MiB。暂不支持流式、工具调用、图片、语音、专有认证头或仅支持 Responses 的服务。`store=false` 不等于保证服务商不留存数据。

上限包含每天调用次数、并发数固定为 1、每次调用预留的估算金额。失败也计入预留，避免不确定请求反复计费；金额来自用户设置，**不是实际账单或精确 token 费用**。每日窗口支持 UTC 或 Asia/Shanghai。更多授权区别与一手资料见 [COMPATIBILITY.md](docs/COMPATIBILITY.md)。

开发本项目所用的 Codex/ChatGPT 授权与运行系统的模型授权分开；本项目没有读取你的 ChatGPT 登录态、Cookie 或订阅额度。也没有启动 OpenClaw 高权限网关。

## 备份、恢复和遗忘

详见 [docs/DATA_AND_PRIVACY.md](docs/DATA_AND_PRIVACY.md)。核心规则：

- `data/state.sqlite3` 是会话、摘要和记忆；`data/guard.sqlite3` 是遗忘、去重、额度与确认记录，恢复时不能被旧副本覆盖。
- 先停止应用，再做备份：

```powershell
.\scripts\windows.ps1 -Action backup -Path backups/content-001.zip
```

- 备份压缩包只含内容库和清单，**另行保存最新的 `data/guard.sqlite3`**。每次遗忘/修改后更新它的安全副本，不仅依赖当初的内容备份。
- 恢复会替换当前内容库、丢失备份后的未备份聊天；必须显式确认：

```powershell
.\scripts\windows.ps1 -Action restore -Path backups/content-001.zip -Confirm
```

- 新电脑需要提供旧电脑停止应用后复制的最新 guard：

```powershell
.\scripts\windows.ps1 -Action restore -Path backups/content-001.zip -Guard D:\private\guard.sqlite3 -Confirm
```

缺失/不匹配的账本将拒绝恢复；已经存在的账本不接受外部覆盖。旧备份中的已删除/被取代记忆会被账本再清除；备份后才写入的新值不会凭空出现，需要重新录入。

数据是本机明文 SQLite。日志为 `data/logs/audit.log`，最多 1 MB × 4 份，只记录时间、事件散列、固定状态/错误代码，不记录正文、姓名或密钥。数据库、日志和备份默认在 Git 忽略范围内；请使用自己电脑账户的访问权限保护它们。

## 代码入口与扩展

| 文件 | 职责 |
|---|---|
| `src/wechat_memory/adapters.py` | 事件/身份契约、模拟收发；没有真实 SDK |
| `engine.py` / `operations.py` | 白名单、顺序、去重、调用预算、发送状态 |
| `memory.py` / `store.py` | 显式记忆、上下文摘录、遗忘账本 |
| `backup.py` | 内容备份与账本保护的恢复 |
| `models.py` | 假模型、可选文本 HTTP 客户端 |
| `runtime.py` / `cli.py` | 单实例锁、控制命令、模拟器 |
| `config.py` / `audit.py` | 严格配置和元数据日志 |
| `wechat_probe.py` / `uia_*.ps1` | 独立只读结构诊断；不接通消息、身份、模型或 SQLite |
| `callback_inbox.py` / `offline_check.py` | 有界回调队列、订阅撤销、临时数据的离线演练 |
| `tests/` | 自动化行为和子进程/本地 HTTP 测试 |

未来 Windows 适配器必须提供稳定消息 ID、真实发送方/会话身份、消息原始发生时间；不能仅凭昵称匹配。还须在实际发送动作前再次验证目标、明确处理未知结果。详见 [docs/WINDOWS_NEXT.md](docs/WINDOWS_NEXT.md)。

## 微信只读诊断

用户已确认本次登录准备完成。以下是只读结构探测命令，当前实机结果见上方说明：

```powershell
.\scripts\windows.ps1 -Action probe-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe'
```

此命令不启动或操作微信、不创建配置/数据库，只输出版本、匹配进程/主窗口数量、控件类型与可见性计数。最多遍历 256 个控件、深度 16，15 秒超时结束子进程；不读取名称、正文、二维码、AutomationId 或 RuntimeId。`structure_observed` 只表示读到了子控件，不证明登录、联系人身份或可监听。`not_running` 表示指定路径的客户端未运行；`no_window` 也可能只是窗口隐藏到托盘。身份与监听准备标志始终为 false。详细状态与验收步骤见 [docs/READ_ONLY_PROBE.md](docs/READ_ONLY_PROBE.md)。
