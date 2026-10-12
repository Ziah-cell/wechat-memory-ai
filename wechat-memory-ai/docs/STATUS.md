# 当前状态：v0.1.23 正常窗口方案

2026-10-13 更新。已执行用户取消最小化的指令，微信目标为正常打开、允许非前台和遮挡、不抢焦点。没有创建子代理或工作树，没有启用真实模型、发送或自动回复。

## 已完成

- 从工作副本删除 98 个 Git 跟踪文件：92 个内部采集研究源码/测试、最小化能力模块和 5 组专用测试；普通读取中的 selection/background/window-state/inbound-capabilities 分支与允许最小化例外也已删除。
- 共清理 17,263 个本地文件、496,578,071 字节（约 474 MiB），包含研究程序、重复源码、EXE、工具链、构建缓存、旧包及过期包清单。精确本机清单在 data/window-open-cleanup-20261012/deletion-manifest.json，脱敏范围见 [558](evidence/558-window-open-cleanup.json)。Git 历史未重写。
- 保留普通窗口核心、模型/记忆/偏好、个人配置与 .env；5,485 个旧研究数据/日志文件的大小与修改时间未变。普通 UIA/视觉/OCR 夹具与通用防待机功能保留。旧报告和旧入口内容标为历史，源码哈希不再声明可在工作副本校验。
- 原生、Python 与 PowerShell 入口均拒绝已删除模式。最小化只保留停止保护；不自动恢复或重绑。普通读取继续输出有界耗时诊断；旧模式状态显示 unsupported，不伪称为 visual 运行。
- 完整发现 345 项测试：332 通过、13 项此前禁止重试的原生实验显式跳过，53.863 秒；0 失败、0 错误。离线 wheel 构建和安装演练通过，包内没有被删除的模块/接口。

## 当前实机边界

**当前目标已改为此前可读的旧测试号，用户已授权正文及遮挡只读验证。** 新号在正常窗口下的 .NET、原生 UIA、UIA8 均无私聊标识（[570](evidence/570-restored-uia-comparison.json)）；用户手动准备旧号后，三接口均取得私聊根标识（[574](evidence/574-previous-account-uia-comparison.json)），客户端版本复核仍为 4.1.15.50。这支持账号/登录会话相关差异，但未证明微信内部原因或新号永久不可读。用户取消返回新号复查，选择继续旧号；授权记录见 [577](evidence/577-previous-account-readonly-scope.json)。

旧号在用户确认**已覆盖且未最小化**后，连续 3 次视觉快照及 1 次联合读取成功：9 个列表项、4 条非空文本，5 次原生调用无超时。窗口非前台，每次 9 点均命中其他窗口，95 次前台采样无切换或目标前台样本（[579](evidence/579-covered-open-window-live.json)）。补查窗口整体与内容区，各 1,089 点（含边界）均命中其他窗口，绑定复查通过，80 次前台采样无切换（[580](evidence/580-covered-window-geometry.json)）。前台窗口矩形单独不能完整包含目标；命中采样不证明逐像素遮挡，20 ms 请求间隔的采样不等于连续事件监听。此前部分遮挡结果保留在 [575](evidence/575-previous-account-open-window-live.json)。未保存正文/图像、未发送、未调用模型、未写真实记忆。

579 方向为 3 条来信候选、1 条几何不合格而未知；没有滚动模式，历史/底部边界未知。静态文本数量变化不能当作新事件通过。576 曾观察到输入框声明可写 ValuePattern 和 TextPattern，发送按钮标签候选支持 Invoke 但当时禁用；只检查元数据，没有写入或调用（[576](evidence/576-open-window-input-metadata.json)）。本轮未重测发送控件。联系人身份、方向、历史、新事件、去重和不抢焦点发送仍需分别验证。

此前全部最小化导致的诊断顺序问题已修复：在 UIA 访问前返回 `window_minimized`，实机为 0 快照（[568](evidence/568-open-window-preflight-live.json)）。最初空标识记录不能追溯认定均由最小化引起。Computer Use 运行环境另有初始化故障，没有访问微信（[572](evidence/572-computer-use-initialization.json)）；普通原生读取不依赖该工具。

此次修正后最新全量回归：346 项发现、333 通过、13 跳过，0 失败/错误，49.471 秒（[567](evidence/567-open-window-preflight-regression.txt)）。新增测试仅使用内存中的窗口状态和回调，不重试被禁止的原生 UI/位图实验。

2026-10-13 首次继续检查在 `window_minimized` 处停止，0 快照（[578](evidence/578-open-window-occlusion-live.json)）；用户恢复并确认覆盖后取得上述 579/580 结果。静态遮挡检查已完成。当前没有启动常驻监听，旧 standby 监听保持停止，自动回复关闭。详见 [窗口验证](OPEN_WINDOW_VALIDATION.md)。

下一步核验旧号的新事件、历史/去重和发送前置条件；不恢复被取消研究、不放宽绑定、不使用昵称/坐标猜测联系人。真实模型、发送、自动回复保留最终确认边界。活动计划：[WINDOW_OPEN_PLAN.md](WINDOW_OPEN_PLAN.md)。
