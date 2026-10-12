# v0.1.23 测试结果（2026-10-13 更新）

最新运行 `python -X utf8 scripts/test.py`：**346 项发现，333 项通过，13 项明确跳过，0 失败/错误，49.471 秒**。[完整输出](evidence/567-open-window-preflight-regression.txt)。

新增一项纯内存原生发现契约测试，不创建窗口、不访问微信：全部窗口最小化时 UIA 回调不得执行；空窗口、缺失标识、重复目标和已最小化目标仍停止，唯一正常私聊目标可返回。修正前以 `UIA must not run` 失败，增加前置检查后通过；实机返回 `window_minimized`、0 快照（[568](evidence/568-open-window-preflight-live.json)）。这是停止保护验证，不是最小化读取或正常遮挡读取成功。

上一轮清理后完整验证为 345 项发现、332 项通过、13 项跳过、53.863 秒（[563](evidence/563-open-window-regression.txt)）。

跳过范围仍为 NativeProbeTests、NativeOcrCheckTests、NativeVisualTextTests、VisualBitmapTests 共 13 项；本次将其显式标记，普通 test 入口不再意外执行此前禁止重试的原生实验。不是“345 项全部通过”。

新增验证包括：旧 Python/PowerShell reader 参数在启动前拒绝、不创建状态目录；原生四个旧参数在访问客户端前拒绝；旧状态不伪称为 visual；UIA 标识缺失只读一次即停止、不交付消息。既有最小化停止、绑定、连续性、去重、超时、记忆/模型和暂停/停止回归继续保留。

最初 2 项新边界测试出现 3 个预期失败：旧 CLI 仍允许两个模式启动、旧状态仍暴露最小化字段。修复后的首次 342 项发现、329 通过/13 跳过，42.189 秒；补充诊断后的中间 344 项发现、331 通过/13 跳过，43.170 秒；该轮最终结果为 563，本次继续修正后的最新结果为 567。没有为了保留旧 382 数字运行已删除的测试。

离线 wheel 构建、安装及 installed offline-check 通过：23 Python 模块、5 原生资源，未包含 retired 模块或研究代码。网络关闭、假模型、临时数据、无发送。[包核验](evidence/564-open-window-package.json)。旧 ZIP/构建副本/包清单已删除；验证产生的临时包及新构建目录也已清理。

初期新号验证未通过读取前置条件：两次 `private_window_not_unique` 旧诊断和一次 `window_identity_unavailable` 新诊断全部保留。[559](evidence/559-open-window-live-read.json)、[560](evidence/560-open-window-live-read.json)、[561 结构](evidence/561-open-window-structure.json)、[562 新诊断](evidence/562-open-window-live-diagnostic.json)。这些不是消息读取或发送通过记录。

后续用户确认更换账号，并选择旧号继续只读验证：旧号三种 UIA 接口均可见私聊根标识（[574](evidence/574-previous-account-uia-comparison.json)）。非前台、部分遮挡下 3 次视觉快照及 1 次联合文本读取成功，取得 3 条非空文本；每次 9 点中 6 点命中其他窗口、调用前后前台相同（[575](evidence/575-previous-account-open-window-live.json)）。输入框可写、发送按钮候选支持 Invoke 但当时禁用，仅查询元数据（[576](evidence/576-open-window-input-metadata.json)）。未发送、未调用模型、未写真实记忆或保存正文/图像。可靠方向、历史/新事件和发送仍未验收，详见 [实测说明](OPEN_WINDOW_VALIDATION.md)。此阶段无产品代码改动，未重复运行完整回归。

2026-10-13 首次只读复查在 `window_minimized` 处停止，0 快照、未发送/调用模型/写真实记忆；29 次前台采样未观察到切换，检查前后前台相同（[578](evidence/578-open-window-occlusion-live.json)）。目标未绑定，不能统计其前台采样数。

用户随后确认已覆盖且未最小化，[579](evidence/579-covered-open-window-live.json) 连续 3 次视觉快照均为 9 项/4 条文本，联合读取 4 条非空文本、3 条来信候选/1 条未知文本；5 次原生调用无超时，最长 1,027 ms。目标非前台、9 点均命中其他窗口；95 次前台采样无切换或目标前台样本。[580](evidence/580-covered-window-geometry.json) 的绑定前后复查通过，窗口整体与内容区各 1,089 点（含边界）均命中其他窗口，80 次前台采样同样无切换。前台窗口矩形单独不能包含目标；这些采样不证明逐像素不透明覆盖或采样间焦点不变。静态遮挡检查完成，未自动发送、调用模型、写记忆或保存正文/图像；未凭文本数量变化认定新事件。本轮仅增加脱敏证据与文档，未改产品代码或重复执行全量回归。

此前测试历史见 [归档](history/TEST_RESULTS-before-window-open.md)。旧研究源码已经删除，原报告的 hash/冻结源码描述仅代表当时事实。
