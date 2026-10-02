# v0.1.9 只读方向与控件复用候选

这些模式用于继续验证普通个人微信接入，均未接入 Engine、模型、记忆或发送器。`sender_verified/history_boundary_verified/real_send_supported/model_called` 始终为 false。原视觉诊断和普通内容观察仍独立；v0.1.9新增同一次有界调用内的正文/方向联合候选，不能将其当作已确认来信。

## 正文与方向联合观察

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --observe-visual-occurrences --seconds 300
```

先将 `$Python` 设置为本机实际Python路径，在项目目录执行。该参数与其他所有观察/诊断参数互斥。原生 `--visual-text` 在相同窗口绑定中，先读取每行正文/token/类型/位置，再捕获内存位图并分类，随后重读整列并逐行比较。数量、顺序、类型、正文、编号或位置变化则以固定错误停止；不会输出半批结果。旧 `--inspect-visual` 仍不读取消息 Name。

Python只接受独立的 `visual_text_snapshot` 协议，不接收普通正文或纯视觉快照。新模式沿用至少两行连续后缀锚点、全部已见token/正文组合记录及4096上限。正文与类型摘要仅用于一致性比较，方向不能使旧组合绕过去重。

同一组合曾取得的来信/自身方向证据保存在有界内存中；后来出现相反的明确方向则停止，即使中间经历过未知状态。裁切造成的 `unknown` 与明确方向之间变化允许继续，不删除先前证据、不增加历史行的候选计数。方向证据与分类计数仅在整批被接受后提交；未知的新文本仍输出为未知候选，以后变得可辨认不会补发或追认旧观察。

报告 `mode=visual_occurrence_candidates`，新增 `incoming_candidate_texts/self_candidate_texts/unknown_candidate_texts` 三个累计文本计数。正文只在受控管道和内存中传递；日志没有正文、联系人或UI令牌。这里没有自身消息自动回复，也没有把来信候选交给模型。

**前后复核不是原子截图。** 捕获期间变化后又恢复、各字段间短暂不一致、视觉误判及后来同步的历史仍可能无法观察。新模式只改进正文与方向的关联证据，不把发送方/历史标志改为true。

本轮已恢复独立窗口。普通候选模式[126](evidence/126-live-occurrence-monitor.txt)已建立基线并在300秒内完成224次读取，新增文本0；这证明基线连续读取，不证明新消息检测通过。联合读取的三次独立基线检查[131](evidence/131-live-joined-baseline.json)均为9行/7文本、4来信候选/1自身候选/2未知，无历史回放。本轮视口与v0.1.8的5/1/1结果不同，保留未知，不宣称真实方向识别已全部通过。联合有界监听记录在[130](evidence/130-live-visual-occurrence-monitor.txt)，受控新来信验收仍待输入。

## 视觉方向检查

在 `wechat-memory-ai` 目录，用实际 Python 路径设置 `$Python`：

```powershell
& $Python scripts/listen-wechat.py --client-path 'D:\软件\Weixin\Weixin.exe' --inspect-visual
```

保持唯一测试好友的独立聊天窗口可见且不最小化。原生程序沿用客户端完整路径及进程/启动时间/窗口/根/列表绑定，在子进程中使用物理坐标与 `PrintWindow(PW_RENDERFULLCONTENT=2)`。窗口位图只保留在内存；不保存、输出或上传截图，不读取消息 Name。调用受原有8秒子进程总超时限制。

仅文本行进入分类：一侧头像区域有足够像素差异、另一侧头像区域为空，且同侧气泡颜色匹配时，才给出 `incoming_candidate` 或 `self_candidate`。左侧需中性灰气泡，右侧需绿色气泡。黑图、空图、双侧证据、裁切、行与列表不对齐、异常背景/尺寸/DPI均保持 `unknown`。只输出三类数量。缺少绿色不能直接作为来信证据。

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

新增视觉7项、出现候选11项；候选测试先失败[116](evidence/116-occurrence-red.txt)、测试契约修正后仍失败[117](evidence/117-occurrence-contract-red.txt)、实现后11项通过[118](evidence/118-occurrence-targeted.txt)。原严格监听33项通过[119](evidence/119-strict-live-regression.txt)。完整168项通过[121](evidence/121-occurrence-visual-full-suite.txt)，具体环境与审查以 [TEST_RESULTS.md](TEST_RESULTS.md) 为准。

v0.1.9新增12项，先失败[127](evidence/127-visual-occurrence-red.txt)与[132](evidence/132-visual-unknown-transition-red.txt)，定向12/12通过[133](evidence/133-visual-unknown-transition-fixed.txt)。包括原生行值复核、严格联合协议、模式隔离、方向计数、旧组合重现、未知转变及跨未知状态的方向冲突。完整测试以 [TEST_RESULTS.md](TEST_RESULTS.md) 为准。

后续先完成受控来信的连续观察，保留重复旧组合时的停止；再验证历史滚动/同步、自身过滤、窗口切换、最小化/锁屏/RDP和长期运行。尚未取得这些证据，不能将候选接入真实模型或发送。
