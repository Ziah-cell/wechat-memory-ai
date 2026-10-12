> 2026-10-13：本文保留既往受控测试及普通窗口组件说明。当前用户选定旧测试号，已完成用户确认覆盖状态下的非前台静态读取，真实桥接未完成；最新状态与范围以 [STATUS](STATUS.md)、[窗口验证](OPEN_WINDOW_VALIDATION.md) 为准。最小化路线已删除，旧测试成功不代表当前非前台/遮挡收发成功。

# v0.1.13 有人监督的只读预检与方向候选

这些模式用于继续验证普通个人微信接入，均未接入 Engine、模型、记忆或发送器。`sender_verified/history_boundary_verified/real_send_supported/model_called` 始终为 false。原视觉诊断和普通内容观察仍独立；v0.1.9新增同一次有界调用内的正文/方向联合候选，不能将其当作已确认来信。

## 新验证文字后的只读预检

v0.1.12新增显式 `--preflight`，由 `PreflightSession` 包装联合候选会话。它先丢弃基线与验证文字之前的观察，只有本轮生成的验证文字被新观察到后，才返回后续批次的来信方向候选。底层候选计数仍包含被丢弃的观察，不能用 `candidate_texts` 或 `incoming_candidate_texts` 代替预检返回计数。

先将 `$Python` 设置为本机实际Python路径，在项目目录执行。该参数与其他观察/诊断模式互斥：

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --preflight --seconds 300 --until-texts 2
```

1. 首次非空、已绑定快照只建立基线；随后生成本轮随机验证文字，由一次 `preflight_challenge` 事件输出。空列表尚未建立基线时不会生成。每次重新启动都生成新文字，旧会话文字不能开启新会话。
2. 由测试方在同一受控会话中发送本轮文字。它必须作为新观察出现一次、方向为 `incoming_candidate`，且是当前可见列表最后一条非空文本；列表中也只能有一次该文字。基线碰撞、自身/未知方向、重复或非末尾验证文字均以固定原因停止。
3. 验证文字出现前的所有候选以及包含验证文字的整批候选全部丢弃，包括同批其他来信。`marker_boundary_observed=true` 只表示这次受控标记条件已观察到，不会把该批重新交付。
4. 后续批次只返回 `incoming_candidate`；自身与未知文本分别计入 `filtered_self_texts/filtered_unknown_texts` 后永久丢弃，以后方向变清楚也不补发。再次新观察到本轮验证文字会关闭预检，整批不返回。

报告 `mode=supervised_readonly_preflight`，状态包括 `waiting_baseline`、`waiting_marker`、`armed`、`closed`；`post_marker_incoming_candidates` 才是通过预检的后续来信候选数。`--until-texts 1..256` 仅按这些返回候选计数，基线、验证文字、自身和未知均不计，同批仍不截断。预检必须设有限的 `--seconds 1..3600`（默认30秒），即使有数量目标也不允许0秒。到达数量/期限、错误或中断后关闭，不自动重新建立基线或恢复；重启必须重新验证。保留每次原生调用8秒超时、绑定、连续性、方向冲突和4096出现组合上限。

此模式必须有人监督，会话期间不得浏览历史。现有能力检查没有可信的到底信号：列表无 `ScrollPattern`（[101](evidence/101-live-identifier-capabilities.json)），祖先滚动容器/相关垂直滚动条诊断暂缓，尚未实现。随机验证文字不证明服务器时间、发送方身份或排除随后同步的历史；`sender_verified/history_boundary_verified/server_message_ids_available/real_send_supported/model_called` 继续为false，没有 Engine、模型、记忆或发送调用。普通报告不输出聊天正文、联系人或UI令牌；单独的 `preflight_challenge` 事件只提供程序生成的本轮验证文字。

这次实机预检已按[177](evidence/177-live-preflight-incoming-pass.json)完成：369次快照，完整标记批次丢弃1文本，之后2条来信候选达到目标、关闭并退出0。被Git忽略的 `data/live-preflight-20261002.jsonl` 是已完成的历史日志；176的等待状态已被后续结果取代，不要重复该次验收。每次新会话仍需新标记，本文不保存实际验证文字。

## 指定窗口消息源与读取期间变化

v0.1.13新增库级`ReadOnlyWeChatSource`，必须显式提供同一授权窗口的expected_binding。`NativeReader`首次原生调用即经私有管道携带该约束，既有C#在读取消息Name前校验；失败不改绑其他窗口。源只在创建线程中串行poll，期限1–3600秒，沿用上述新标记和永久方向过滤规则。关闭、到期或错误后，源的`is_current(candidate)`检查返回false，send始终拒绝。它没有CLI接入，也未接入Engine、模型、SQLite/记忆或发送；接口见 [LIVE_SOURCE.md](LIVE_SOURCE.md)。绑定约束只确认当前窗口实例，不证明联系人身份。

已绑定的联合读取只对原生`visual_snapshot_changed`最多尝试3次子调用；所有调用及等待共享原8秒单调时钟预算，等待最多50毫秒且不超过剩余时间。每次保持同一绑定，中间失败不提交Python会话检查点，超过预算的成功结果也不交付。首次未绑定读取、普通/诊断模式，以及其他错误、超时、协议或绑定失败均不重取，不自动重新建立基线或解锁。只读属性`snapshot_change_retries`累计实际额外子调用。该机制与下节原生进程内的空前景捕获重取不同；目前只有纯Python重取测试，尚未取得真实恢复证据。

## 已取得的实机证据与历史反例

| 证据 | 实际结果与范围 |
| --- | --- |
| [159](evidence/159-live-1005-arrivals.json) | 保持原基线运行的v0.1.10监听在第1026/1028次快照捕获两条1005来信方向候选；累计3新增行、2文本、2次顶部移除、1次token复用，达到目标后退出0。这次到达捕获已通过，不能归为v0.1.12预检通过。 |
| [160](evidence/160-live-restart-baseline.json)、[162](evidence/162-live-restored-baseline.json) | 新会话/窗口恢复后各三次读取均返回0观察；当前可见内容只进入基线，未自动回放或恢复旧会话。 |
| [161](evidence/161-live-window-history-stops.json)、[163](evidence/163-live-older-history-negative.json) | 所测历史上下滚动及一次最大化布局变化以 `message_continuity_lost` 停止；最小化以 `window_minimized` 停止。这些有限负例不覆盖所有历史导航。 |
| [164](evidence/164-live-deeper-history-negative.json) | 更深历史视口滚动后，底层联合会话仍接受2条旧文本为未知方向候选，返回2观察。连续性通过不等于新到达，不能将此结果抹去或推广为已阻止历史。 |
| [171](evidence/171-live-preflight-history-negative.json) | 预检重现相同的旧历史追加形状：底层2条候选、预检返回0、`pre_marker_discarded_texts=2`，仍为 `waiting_marker`。仅验证标记之前的阻挡，未验证标记之后的历史隔离或正向放行。 |
| [177](evidence/177-live-preflight-incoming-pass.json) | 新随机标记和后续两条来信正向准入通过，达到目标并关闭；不证明任意历史或稳定发送方身份。 |
| [183](evidence/183-live-self-listener-timeout.json)、[184](evidence/184-live-self-filter-component.json)、[185](evidence/185-self-sample-direction-check.json) | 首次监听超时无新增；随后样本3次判incoming，核查确认实际是左侧消息，并非自身样本。 |
| [187](evidence/187-live-self-filter-inconclusive.json)、[188](evidence/188-live-self-visual-reasons.json) | 真正自身到达期间31快照后因`visual_snapshot_changed`停止、无新增，尚未通过。之后联合分类unknown，另次纯视觉检查为`edges_inconsistent`；两次读取不是原子证据。 |
| [189](evidence/189-live-maximized-self-component.json) | 最大化后已可见自身消息3/3判self，共享过滤返回0，仅历史消息组件通过；未验证新自身到达或已解锁会话过滤，分类阈值未改。 |
| [193](evidence/193-live-bound-source-baseline.json) | 显式绑定消息源三次基线零交付、关闭后poll/send拒绝、错误窗口绑定拒绝通过；新候选实际交付未验证。 |

## 视觉失败原因与空证据重取

v0.1.11的 `--inspect-visual` 另报告 `capture_attempts`（1–3）及11个固定原因的 `reason_counts`，包括零计数。原因只表示首个未通过的检查，不能单独证明捕获API或微信渲染的根因：

| 原因 | 含义 |
| --- | --- |
| `geometry_invalid` | 位置、范围或缩放不符合分类条件 |
| `background_unsupported` / `edges_inconsistent` | 背景或边缘检查未通过 |
| `avatar_inconclusive` | 左右头像证据不能唯一支持一个方向 |
| `foreground_evidence_absent` | 几何/背景/边缘已通过，两个头像及三个气泡采样计数全零 |
| `incoming_bubble_unconfirmed` / `incoming_green_conflict` | 左侧中性气泡证据不足或绿色证据冲突 |
| `self_bubble_unconfirmed` | 右侧绿色气泡证据不足 |
| `incoming_evidence` / `self_evidence` / `not_text` | 已取得对应候选证据或属于非文本行 |

纯视觉协议严格校验原因、方向、类型及捕获次数；纯视觉分支仍不读取Name，不输出令牌、正文、图像或逐像素值。联合正文协议保持原结构，不加入这些诊断字段。

只有整批中至少一条 `foreground_evidence_absent`，且其他行仅为该原因、几何不适用或非文本，才允许下一次捕获。最多三次，相邻重取等待50毫秒；仍受原8秒子进程超时约束，不能保证阻塞API调用能完成三次。每次前后复核原始绑定、列表、顺序、token、类型、矩形（联合模式再核正文）；有变化立即停止，不重建基线、不输出半批。每次清除上次结果，返回一整张最终捕获的分类，绝不拼接各次的有利结果。其他未知或混合证据不触发重取，耗尽后仍保持未知。

实现前[150](evidence/150-live-visual-reasons.json)的12次有一次5条头像不确定；进一步细分后的[153](evidence/153-live-empty-evidence.json)为30次中一次5条前景证据全零，该记录尚未启用重取。实现后[154](evidence/154-live-visual-recovery.json)60次全部5来信/1几何未知，59次首取、1次第二次捕获恢复。未证明三次耗尽、瞬态变更/恢复、其他主题/窗口状态或任意头像场景；所有验证标志不变。1005长监听当时保留启动时的v0.1.10基线，随后已按目标完成，见[159](evidence/159-live-1005-arrivals.json)。

## 普通联合候选的等待方式与历史记录

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --observe-visual-occurrences --seconds 0 --until-texts 2
```

v0.1.10显式零秒配合数量目标会持续等待，直到接受至少两条新增非空文本、发生错误或Ctrl+C。基线不计入目标，同批不截断；自身/未知方向也计入数量，所以必须另核对三个方向计数。保留每次原生读取8秒超时、绑定、连续性和4096容量保护，不自动恢复。需要整体等待时限时设1–3600秒，默认30秒。单次诊断禁止数量目标。

最后报告为 `completed`，原因 `text_limit_reached` 或 `deadline_reached`；退出码0不能替代来信验收。曾用于1003的300秒监听218次读取、1004的3600秒监听2301次读取均为新增0，后续才在窗口里核对到各两条测试文字。真实到达时间未知，不能将后来可见解释为监听捕获通过。[记录138](evidence/138-late-live-inputs.json)。

1004当时行方向还有波动：四次检查分别为1来信/1未知、2来信、2来信、2未知。UIA正文一致性与视觉内容完整性是不同证据；保留未知，未修改分类阈值或补发旧观察。随后建立的1005持续等待已捕获两条来信方向候选并正常结束，汇总见[159](evidence/159-live-1005-arrivals.json)；原始历史日志保留在被Git忽略的 `data/live-acceptance-1005-20261002.jsonl`，不再作为活动监听处理。

## 正文与方向联合观察

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --observe-visual-occurrences --seconds 300
```

先将 `$Python` 设置为本机实际Python路径，在项目目录执行。该参数与其他所有观察/诊断参数互斥。原生 `--visual-text` 在相同窗口绑定中，先读取每行正文/token/类型/位置，再捕获内存位图并分类，随后重读整列并逐行比较。数量、顺序、类型、正文、编号或位置变化则以固定错误停止；不会输出半批结果。旧 `--inspect-visual` 仍不读取消息 Name。

Python只接受独立的 `visual_text_snapshot` 协议，不接收普通正文或纯视觉快照。新模式沿用至少两行连续后缀锚点、全部已见token/正文组合记录及4096上限。正文与类型摘要仅用于一致性比较，方向不能使旧组合绕过去重。

同一组合曾取得的来信/自身方向证据保存在有界内存中；后来出现相反的明确方向则停止，即使中间经历过未知状态。裁切造成的 `unknown` 与明确方向之间变化允许继续，不删除先前证据、不增加历史行的候选计数。方向证据与分类计数仅在整批被接受后提交；未知的新文本仍输出为未知候选，以后变得可辨认不会补发或追认旧观察。

报告 `mode=visual_occurrence_candidates`，新增 `incoming_candidate_texts/self_candidate_texts/unknown_candidate_texts` 三个累计文本计数。正文只在受控管道和内存中传递；日志没有正文、联系人或UI令牌。这里没有自身消息自动回复，也没有把来信候选交给模型。

**前后复核不是原子截图。** 捕获期间变化后又恢复、各字段间短暂不一致、视觉误判及后来同步的历史仍可能无法观察。新模式只改进正文与方向的关联证据，不把发送方/历史标志改为true。

v0.1.9历史记录：窗口恢复后，普通候选模式[126](evidence/126-live-occurrence-monitor.txt)在300秒内完成224次读取，新增文本0；这只证明基线连续读取。联合读取的三次独立基线检查[131](evidence/131-live-joined-baseline.json)均为9行/7文本、4来信候选/1自身候选/2未知，无历史回放。该视口与v0.1.8的5/1/1结果不同，不能宣称真实方向识别已全部通过。联合有界监听记录在[130](evidence/130-live-visual-occurrence-monitor.txt)；后续1005到达捕获结果见[159](evidence/159-live-1005-arrivals.json)。

## 视觉方向检查

在 `wechat-memory-ai` 目录，用实际 Python 路径设置 `$Python`：

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --inspect-visual
```

保持唯一测试好友的独立聊天窗口可见且不最小化。原生程序沿用客户端完整路径及进程/启动时间/窗口/根/列表绑定，在子进程中使用物理坐标与 `PrintWindow(PW_RENDERFULLCONTENT=2)`。窗口位图只保留在内存；不保存、输出或上传截图，不读取消息 Name。调用受原有8秒子进程总超时限制。

仅文本行进入分类：一侧头像区域有足够像素差异、另一侧头像区域为空，且同侧气泡颜色匹配时，才给出 `incoming_candidate` 或 `self_candidate`。左侧需中性灰气泡，右侧需绿色气泡。黑图、空图、双侧证据、裁切、行与列表不对齐、异常背景/尺寸/DPI均保持 `unknown`。报告三类数量、固定原因计数及捕获次数。缺少绿色不能直接作为来信证据。

捕获前后检查窗口位置、DPI及可见/最小化状态；随后重读列表边界和所有行的token、类型、矩形。变化时返回固定 `visual_capture_unavailable` 或 `visual_snapshot_changed`，不输出外部异常。检查没有读取消息正文，因此不能证明相同token/类型/矩形中的内容未发生原地变化；本模式不提供正文与方向的原子联合结果。

真实结果保留全部尝试：默认 PrintWindow 参数0虽然返回成功，但消息区域为空，7文本均未知（[109](evidence/109-live-visual-direction.json)）；内存像素计数确认该限制（[110](evidence/110-live-visual-metrics.json)）。改用参数2后得到5条来信候选、1条自身候选、1条未知（[111](evidence/111-live-visual-fullcontent-probe.json)）；产品代码连续3次绑定检查计数一致（[113](evidence/113-live-visual-bound-check.json)）。实机只覆盖当前微信4.1.15.50、浅色、150%缩放的测试窗口。未知项没有被强行归类。

18组虚构位图覆盖浅色/深色、缩放、双侧/空白/黑图/裁切、颜色和头像不一致等条件。真实WinForms捕获夹具使用屏幕内、无激活的临时窗口；原离屏夹具在参数2下返回未知的失败仍保留于[112](evidence/112-visual-fullcontent-targeted.txt)，修正夹具位置后7项定向通过[114](evidence/114-visual-fullcontent-fixture-fixed.txt)。不能将夹具覆盖说成各种真实头像、主题、长消息、混合显示器或遮挡场景均已验证。

技术来源：[Microsoft PrintWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)、[GetWindowRect的DPI说明](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect)、[Windows SDK中的PW_RENDERFULLCONTENT定义](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/WinUser.h)。调用成功不等于内容完整或分类正确。

## 控件复用观察

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --observe-occurrences --seconds 300
```

必须显式选择该模式，且不能与三个单次检查同时使用。不带该参数仍使用原来的严格 `ReadSession`：任何已见token作为追加行重现都停止。

候选模式沿用相同绑定和顺序约束：首次非空快照只建立基线；只接受完整旧前缀后的追加，或至少两个完全一致的旧连续后缀/新前缀锚点后的追加。只有移除、锚点改动/重排、弱重叠或窗口/列表变化仍停止。

与默认模式的唯一区别是追加项的重现判断：

- 本次会话从未出现过的token与类型/正文摘要组合，可成为UI出现候选；已经见过的token如果内容改变，可以计入候选。
- 任何曾出现过的相同token与摘要组合重现，整批以 `occurrence_reappeared` 停止。这可能拒绝一条真实的相同来信，因为界面证据不足以区分它与旧记录，不能自动重试。
- 最多保存4096个出现组合，包含基线、非文本和已移出行；复用token的不同内容也分别占用容量。超限时 `session_occurrence_limit`，整批不增加计数、不返回部分候选。
- 两条相同文字只要属于不同、此前未见的组合，就分别分配本地会话UUID/序号。摘要用于比较，不作为微信消息ID，也不用于将所有相同文字合并。
- 重启只建立新基线，不回放当前可见内容，不承诺找回停机消息。不自动从停止状态恢复。

报告带 `mode=occurrence_candidates`；`candidate_rows/texts` 取代默认模式的新增观察计数。`reused_token_candidates` 统计复用过的追加token，`seen_occurrences` 是本会话比较组合数。`seen_tokens` 仍是不同UI令牌数。所有报告仅包含固定状态、原因、计数与布尔；正文和UI令牌只经过私有管道/进程内存，历史正文仅保留摘要。

这仍可能观察到后来同步的旧记录，不能证明消息来自当前时刻。视觉方向候选也未提供可靠历史边界。模式成功或退出码0不能作为自动回复就绪条件。

v0.1.8当时实际启动返回 `private_window_not_unique`，快照0、未绑定（[120](evidence/120-live-occurrence-monitor.txt)）；随后 Computer Use 只列出微信主窗口。当前窗口已恢复并重新建立基线，见本页联合观察记录。此前1001/1002的发送确认不能替代此次监听证据。

## 验证与剩余工作

v0.1.13新增共享过滤1项后，预检14项通过[178](evidence/178-shared-filter-targeted.txt)；显式绑定8项、消息源24项、重取10项分别通过180/182/191。独立审查192重复18项绑定/重取纯Python测试，无待修复发现。最新发现250项、选定237/237通过58.384秒，原4类13项原生测试未重跑；范围与证据见 [TEST_RESULTS.md](TEST_RESULTS.md)。这些结果不替代真实新自身到达、消息源新候选交付或重取恢复实测。

v0.1.12历史预检先有[165](evidence/165-preflight-red.txt)预期失败，再有[166](evidence/166-preflight-targeted.txt)定向通过；ASCII输出兼容补测先失败[169](evidence/169-preflight-ascii-red.txt)，当时13项预检测试通过[170](evidence/170-preflight-ascii-green.txt)。覆盖新标记生成、基线碰撞、整批丢弃、后续方向过滤、重复/歧义标记、关闭与有限等待。实机负例见171，后续正向准入见177。

新增视觉7项、出现候选11项；候选测试先失败[116](evidence/116-occurrence-red.txt)、测试契约修正后仍失败[117](evidence/117-occurrence-contract-red.txt)、实现后11项通过[118](evidence/118-occurrence-targeted.txt)。原严格监听33项通过[119](evidence/119-strict-live-regression.txt)。完整168项通过[121](evidence/121-occurrence-visual-full-suite.txt)，具体环境与审查以 [TEST_RESULTS.md](TEST_RESULTS.md) 为准。

v0.1.9新增12项，先失败[127](evidence/127-visual-occurrence-red.txt)与[132](evidence/132-visual-unknown-transition-red.txt)，定向12/12通过[133](evidence/133-visual-unknown-transition-fixed.txt)。包括原生行值复核、严格联合协议、模式隔离、方向计数、旧组合重现、未知转变及跨未知状态的方向冲突。完整测试以 [TEST_RESULTS.md](TEST_RESULTS.md) 为准。

正向准入已完成；后续仍需取得标记后新自身事件过滤、消息源实际交付新候选及有界重取真实恢复的证据。1005与177提供受控来信到达/准入证据，不能消除164的历史反例；锁屏/RDP、其他窗口变化、长期运行及标记后的历史同步均未完整验证。没有可信到底信号，不在预检中浏览历史，不复用旧验证文字；不将候选接入 Engine、模型、记忆或发送。用户自然聊天偏好见 [CHAT_EXPERIENCE.md](CHAT_EXPERIENCE.md)，尚未据此选择或配置真实模型。
