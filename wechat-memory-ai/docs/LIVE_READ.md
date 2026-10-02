# v0.1.13 微信独立只读连接

两条真实相同来信已被持续监听捕获（159），重启基线零回放、最小化停止已实测（160–162）。旧历史起点向下滚动仍会产生候选（164）；新随机标记准入在同样反例中返回0（171）。随后[177](evidence/177-live-preflight-incoming-pass.json)已完成真实正向准入：369次快照，标记批次丢弃1文本，之后两条来信候选达到目标、关闭并退出0。旧`data/live-preflight-20261002.jsonl`已完成，不再等待输入。

v0.1.13新增库级`ReadOnlyWeChatSource`，必须显式传入同一授权窗口的expected_binding，首次原生调用即在读取消息Name前校验该约束。源在创建线程中串行poll，限1–3600秒并沿用新标记准入；关闭、到期或错误后失效，send始终拒绝。实机[193](evidence/193-live-bound-source-baseline.json)完成三次基线零交付、关闭后poll/send拒绝及错误窗口绑定拒绝；尚未验证该封装中新候选实际交付。它没有CLI接入，也未接入Engine、模型、SQLite/记忆或发送，详见 [LIVE_SOURCE.md](LIVE_SOURCE.md)。

真实自身到达过滤尚未通过：183监听超时，184样本虽三次判incoming，但185确认实际在左侧，并非自身样本。真正自身输入期间[187](evidence/187-live-self-filter-inconclusive.json)在31次快照后因`visual_snapshot_changed`停止、无新增；188另次纯视觉诊断为`edges_inconsistent`，不能当作原子联合证据。最大化后[189](evidence/189-live-maximized-self-component.json)对已可见自身消息3/3判self、共享过滤返回0，**仅历史消息组件通过**，未验证新自身到达或已解锁会话中的过滤；分类阈值未改。

已绑定联合读取现在仅对原生`visual_snapshot_changed`最多尝试3次子调用，共享原8秒单调时钟预算（含最多50毫秒且不超过余量的等待）。每次保持同一绑定和Python会话检查点，只交付预算内的最终成功结果。首次未绑定读取、普通/诊断模式、其他错误/超时/协议或绑定失败不重取，不自动重新建立基线或解锁。十项纯Python测试及独立审查通过，真实重取恢复尚未验证，187的失败结论不变。

最新发现250项、**选定237/237通过，58.384秒**，4类13项原生测试未重跑，见194/195与 [TEST_RESULTS.md](TEST_RESULTS.md)。不是全套250项通过，也没有重跑被拒夹具。用户自然聊天偏好已记录为后续需求，未据此选择、配置或调用真实模型。

这只是一种短时、同一授权窗口且不翻历史的受监督检查。它不证明原子UI一致性、发送方身份、任意历史同步或服务器消息ID，原有验证标志仍false。现无可信到底信号，祖先滚动条诊断暂缓。具体运行命令及边界见 [READ_CANDIDATES.md](READ_CANDIDATES.md)。

## v0.1.7及此前实机记录

**v0.1.7当时连续监听未通过。** 当时诊断定位真实 RuntimeId 复用，UIA 元数据不足以验证发送方和历史边界。下面保留固定文本收发与先前修复的历史记录（92、95、101）；最新进展与限制见本文顶部，自动回复仍未启用。

2026-10-01，用户本人完成登录后，实际微信 4.1.15.50 的独立测试私聊窗口能提供消息控件。Computer Use 和项目独立程序均读取成功。初次窗口有 8 个列表项、5 个文本项；原生程序连续 3 次读取并保持同一绑定，没有把已有文字输出为新增观察。证据：[69](evidence/69-live-read-initial.json)、[73](evidence/73-live-read-bound-snapshots.json)。

随后已完成一次真实双向固定文本验收：两条相同来信显示为两个独立左侧气泡，原生读取器也读到两个文本项；用户明确授权的一条固定回复通过 Computer Use 点击一次发送，观察到唯一右侧绿色回复、输入框清空，用户确认收到。该次授权已用完。测试文字核对仅忽略用户省去的空格，不改写真实文本或合并相同文本。脱敏证据：[78](evidence/78-live-exchange.json)。没有调用真实模型、启用自动回复或开发项目发送适配器。

旧有界监听器在 8 行变 9 行、保留旧列表末尾 6 行并追加时间行与两条文本时停止，**没有返回新增观察**。v0.1.6 针对此变化修复 Python 状态机并通过虚构快照回归，后续实机结果如下。

## v0.1.7实机结果（历史记录）

| 检查 | 真实结果 |
|---|---|
| 首次连续监听 | 25次接受快照、2新增行/1新增文本后停止；旧格式无原因，不能推断，见[84](evidence/84-live-continuity-monitor.txt) |
| 中断和恢复 | [87](evidence/87-live-diagnostic-monitor.txt)只有基线，因用户中断未完成；[88](evidence/88-live-resumed-diagnostic-monitor.txt)未建立基线，当时 Computer Use 报告窗口最小化，恢复窗口后再读；[89](evidence/89-live-restored-monitor.txt)接受54次后报旧格式 generic error，原因未知 |
| 新诊断下的两条相同来信 | 第一条接受：7行连续重叠，顶部移除1次，新增2行/1文本。第二条8行连续重叠，但追加项复用已见token，整批因 `message_token_reused` 停止，计数保持不变。见[92](evidence/92-live-native-diagnostic-monitor.txt) |
| 几何与子控件 | 9行中7文本，7文本均横跨列表全宽，无子控件；无法按行位置识别方向。见[95](evidence/95-live-layout.json) |
| UIA 元数据 | 9行中7行有非空 AutomationId，不同值只有1个；另有7个文本行，两项汇总不推断逐行交叉分布。全部行均无 HelpText、ItemStatus、ItemType、LabeledBy、TextPattern，列表无 ScrollPattern，`bottom_observed=null`。见[101](evidence/101-live-identifier-capabilities.json) |

以上表明 RuntimeId 与 AutomationId 均不能直接作为消息身份，当时连续监听、自身过滤和历史边界不满足自动回复前提。该阶段保护保持停止，没有自动重建基线、替换ID或重试。不要求重登或重复已完成的固定回复验收。该阶段真实发送数为0；没有调用模型或写入记忆。v0.1.13的有限重取仅适用于顶部所述已绑定联合读取，不能绕过连续性或绑定失败。

免费上游的 `is_my_bubble` 使用头像区域/绿色像素启发式，而非可验证的发送方字段。该源码是路线参考，不是本机正确性证据；本项目未安装或执行它。若继续视觉路线，需独立处理遮挡、裁切、主题、长消息与历史滚动反例，并保留未知状态，不能将“未发现右侧绿色”直接当作来信。[上游源码](https://raw.githubusercontent.com/Hello-Mr-Crab/pywechat/main/src/pyweixin/WeChatTools.py)（2026-10-01查阅）。

## 运行

保持第二个普通号已登录，只打开一个测试好友的独立聊天窗口，进入 `wechat-memory-ai` 目录：

```powershell
.\scripts\windows.ps1 -Action listen-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe' -ListenSeconds 30
```

v0.1.10时长可设1–3600秒，默认仍为30秒；Ctrl+C停止。Python入口可另用 `--until-texts 2` 在接受至少两条新增非空文本后结束；基线、空文本与非文本行不计入，同批超过目标也整批保留。所有方向均计入目标数量，达到数量不代表来信识别通过。单次诊断不接受该参数。

验收需等待用户输入时，可显式使用 `--seconds 0 --until-texts 2`：不设置整体等待时限，直到目标数量、读取错误或中断。零秒不能单独使用，也不能用于单次诊断。Windows包装入口的 `-ListenSeconds` 支持1–3600秒；持续等待请使用Python入口，见 [READ_CANDIDATES.md](READ_CANDIDATES.md)。没有自动重启或重新建立基线。

首次建立基线，之后每秒尝试读取一次；系统 UIA 单次调用可能使实际间隔变长。编译最多25秒，每次读取最多8秒；已绑定联合读取中的`visual_snapshot_changed`按顶部规则在同一8秒内有限重取，其余读取异常即停止。这两个超时和会话4096项容量在持续等待模式仍生效。正数CLI等待时限在每次读取后检查，最后一次读取可能跨过时限。源码入口是 `scripts/listen-wechat.py`，安装后的命令为 `wechat-memory-listen --client-path ... --seconds 30`。

`status=reading` 与 `window_bound=true` 表示当前窗口已绑定；`observed_new_rows/texts` 是相对于基线新增的 UI 列表项/文本项计数。初始化时列表为空则保持 `initializing`，首批非空行只建立基线。v0.1.10正常结束的最后一条报告为 `status=completed`，`completion_reason` 区分 `text_limit_reached` 与 `deadline_reached`；后者不能算收到目标数量。正常结束退出码0，读取失败或中止仍为 `stopped` / 3，不带正常完成原因。退出码0不表示真实收发验收通过。

`stop_reason` 在正常读取时为 null，停止时只输出固定错误代码。第一次停止原因保留，未知异常转为 `read_failed`；不输出异常正文。`front_evictions` 只累计接受的顶部移除，`seen_tokens` 包含基线及已移出项；失败批次不增加计数。

原生读取可报告 `window_minimized`、`private_window_not_unique`、`window_or_list_changed`、`message_tree_unavailable` 等固定阶段代码；阶段代码表示失败位置，不一定能解释底层根因。超过子进程8秒时为 `native_reader_timeout`；坏输出、未知代码仍为 `native_reader_unavailable`。

新增两个互斥的单次检查（用本机Python路径设置 `$Python`）：

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --inspect-layout
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --inspect-capabilities
```

两者均在限定窗口绑定下运行，不读取消息 Name，不观察新增消息。布局检查只报告文本行全宽/有子控件的数量；能力检查只报告属性/模式存在数量和非空 AutomationId 的不同值数量，不输出其原值。`bottom_observed` 仅在有有效 ScrollPattern 时表达当前滚动位置，**即使为 true 也不证明历史同步完成**。诊断成功退出码0不改变发送方/历史/发送能力标志。

不使用 `config.toml`、API Key 或 OCR 环境，不调用模型、不写入记忆。默认输出没有聊天正文或联系人信息。核心的 `run` 仍为控制台模拟器；这条独立连接没有隐藏的发送开关。

## 读取范围与连续性

- 使用已有系统 .NET Framework x64 编译器临时编译项目自己的 `live_reader.cs`，不安装软件包，结束清理临时程序。缺少编译器时停止。
- 按完整客户端路径限定进程，仅接受唯一的 `ChatSingleWindowwxid_…` 独立私聊窗口。窗口标题或昵称不参与选择；不自动搜索其他联系人。
- 绑定进程、进程启动时间、窗口、窗口 AutomationId 和列表实例。绑定通过私有 stdin 传给原生提供器，在读取消息正文之前检查；读取之后再检查窗口/列表。默认NativeReader首读建立绑定，显式expected_binding则从首次调用起施加约束；ReadOnlyWeChatSource要求显式绑定。不会因旧窗口消失而读取新窗口的正文。
- 最多遍历 1024 个控件、深度 48、列表 256 项、每项 10000 字符。只读取限定窗口内列表项的正文，不打开聊天记录、不滚动、不点击或输入。
- 完整前缀保留时接受追加；顶部旧行移出时，只有旧快照的连续后缀与新快照前缀按 token 和内容摘要完全一致、至少保留两个锚点且有追加行才继续。仅移除无追加、单锚点、无重叠、内部移除/重排/内容变化或列表重建均停止。
- 会话内保留所有已见 token（包括基线和非文本行），最多 4096 个。已移出的 token 不得再次作为新增项，即使正文改变；超限或重现时整批停止，不增加本批计数、不返回部分结果。达到上限后不变快照仍可读取，下一批新 token 到达才停止；不会自动重建基线或恢复。
- 两条相同文字保留为两个条目。本地观察编号是一次读取会话的 UUID 和序号，**不是微信消息 ID**。重新启动时重新建立基线，不回放当前可见记录，也不承诺恢复停机期间消息。

真实正文只在受控子进程管道和进程内存中用于读取与比较，不写入报告、截图文件、数据库或仓库。旧行只保留令牌与内容摘要用于比较，不把内容摘要当成消息身份。

## 已知限制

RuntimeId 只用于同一运行中 UI 实例的比较，可能被复用；AutomationId 也不是跨所有窗口/版本的全局身份保证。[Microsoft RuntimeId 说明](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.getruntimeid)、[AutomationId 说明](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.automationidproperty)。

采样间发生又恢复的变化可能不可见；初始非空列表后续仍可能追加同步的历史记录。因此“新增观察”不等于已证明的新到达微信消息，`history_boundary_verified=false`。发送方方向未取得可靠证据，`sender_verified=false`；当前不会把任何观察自动交给模型、记忆或发送器。

两条相同来信和一次固定回复的人工实机验收已通过，但目视左右方向不等于程序已具备可靠的发送方识别。早期连续监听因token复用失败（92）；随后159已捕获两条来信，177已通过新标记正向准入，160–162完成重启/恢复零回放和最小化停止的有限检查。真实新自身过滤仍未通过，任意历史同步、另一联系人切换、锁屏/RDP和长期稳定性未全面验证；189只验证已可见自身消息的组件过滤。此前不能读取UI的原因没有确定，不把当前结果推广到其他账号/版本。

## 验证

v0.1.7 新增14项用例，定向33项通过，见[100](evidence/100-identifier-count-targeted.txt)。覆盖首次停止原因、计数原子性、未知异常脱敏、CLI传播/中断、原生阶段代码与超时、布局/能力严格协议、无模式不能声称到底、极大整数/非有限几何拒绝、检查模式绑定与历史隔离。完整回归与独立审查以 [TEST_RESULTS.md](TEST_RESULTS.md) 为准。

失败/修复配对：[85/86](evidence/85-live-diagnostics-red.txt)、[90/91](evidence/90-native-diagnostics-red.txt)、[93/94](evidence/93-layout-red.txt)、[96/97](evidence/96-capabilities-red.txt)、[99/100](evidence/99-identifier-count-red.txt)。真实失败证据不会因程序测试通过而改写。

以下为 v0.1.6 验证记录：

v0.1.6 新增 6 项回归，覆盖顶部移除后两条相同文本、锚点/追加要求、旧 token 重现（含正文变化及完整前缀追加）、4096 上限与批次原子性、重启不回放。实现前 19 项、6 errors（其中一个测试有两个失败子例）：[79](evidence/79-live-overlap-red.txt)。实现后 19/19、1.875 秒：[80](evidence/80-live-overlap-targeted.txt)；完整 136/136、30.124 秒、0 失败/错误/跳过：[81](evidence/81-live-overlap-full-suite.txt)。这些是虚构数据回归，不代替修复后的真实新消息监听验收。

版本更新后通过 Windows 项目入口最终复验：`scripts/windows.ps1 -Action test -Python <现有解释器>`，136/136、30.488 秒、0 失败/错误/跳过：[82](evidence/82-live-overlap-final-suite.txt)。

独立只读审查无待修复发现，另行定向测试和内存边界检查通过：[83](evidence/83-live-overlap-review.json)。

以下为 v0.1.5 验证记录：

新增 13 项测试：基线、相同文本、重新启动、绑定变化、已有行变化、空列表后历史加载、正文读取前传递绑定、异常脱敏、超时参数、实际原生编译及临时清理、双 PowerShell 入口与配置隔离。

实现前缺失模块：[65](evidence/65-live-read-red.txt)。测试数据构造错误及修正：[66](evidence/66-live-read-targeted.txt)、[67](evidence/67-live-read-targeted-fixed.txt)。独立审查发现并修复读取前绑定、空列表初始化及文件系统异常脱敏，失败/修复证据：[70](evidence/70-live-read-review-red.txt)、[71](evidence/71-live-read-review-fixed.txt)、[75](evidence/75-live-read-stat-red.txt)、[76](evidence/76-live-read-stat-fixed.txt)。全部审查发现已复验关闭。

完整测试结果见 [TEST_RESULTS.md](TEST_RESULTS.md)。v0.1.5 wheel 已临时构建安装，确认包含原生源码、安装后能编译并拒绝不存在的客户端：[74](evidence/74-live-read-package.json)。该安装验证没有访问真实微信。
