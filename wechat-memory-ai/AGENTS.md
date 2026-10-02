# 项目开发约定

- 当前 v0.1.8：新增 `--inspect-visual`（内存 PrintWindow 完整内容、头像与气泡正证据、只输出方向候选计数）和显式 `--observe-occurrences`（控件复用出现候选）。视觉与正文目前独立，不能拼接成已确认来信；所有发送方/历史/发送/模型标志仍 false。详见 docs/READ_CANDIDATES.md。
- 默认 ReadSession 规则不变；候选模式只在既有连续锚点下允许旧token的新内容。曾见token/内容组合重现或超过4096个组合仍整批停止；本地UUID/序号、内容摘要及UI token均不是微信消息ID。
- 新增18项、完整168/168通过；视觉与候选模式独立审查均无待修复发现。当前视觉实测3次一致：5来信候选/1自身候选/1未知，仅覆盖当前浅色150%环境，不代表各种主题/头像/历史正确。
- 候选监听本轮实机启动未建立基线（120：private_window_not_unique；桌面工具只返回微信主窗口），已请求重新打开同一个独立测试窗口。不要把此前1001/1002发送确认当成本版候选监听通过；无需重登或重做固定回复。真实自动回复仍关闭。

## v0.1.7及此前记录

- v0.1.7 新增固定白名单停止诊断、已接受顶部移除/已见 token 计数、--inspect-layout 与 --inspect-capabilities。诊断不读消息 Name，只输出计数/布尔，不输出属性值、身份或正文。默认连续性规则保持 v0.1.6：至少两个 token/摘要后缀锚点且有追加才接受顶部移除；已见 token 重现或超过 4096 个整批停止。见 docs/LIVE_READ.md。
- 真实新消息监听未通过：证据92接受第一条测试来信后，第二条因 message_token_reused 停止。95/101确认7文本项全宽无子控件；9行中有7行共用1个非空 AutomationId（两项汇总不能推断逐行交叉分布）。无 TextPattern、HelpText/ItemStatus/ItemType/LabeledBy 或列表 ScrollPattern。不把 RuntimeId、共享 AutomationId、正文哈希或截图猜测当成稳定消息ID；不能直接放宽保护后宣称自动回复就绪。
- v0.1.7 新增14项回归，完整150/150通过；独立审查未发现代码缺陷，已修正文档的汇总计数推断。证据与限制以 docs/TEST_RESULTS.md、docs/LIVE_READ.md 为准。
- 用户已授权自主推进至自动回复启用前，无需重复确认常规开发/只读验证权限。真实固定文本收发此前已通过（证据78），一次固定回复授权已用完；无需重登或重做。本轮没有再次发送，自动 AI、项目发送适配器及真实模型未启用；sender_verified/history_boundary_verified 仍 false，不接入 Engine/模型/记忆。

- 核心仍 v0.1.4；新增源码树独立 RapidOCR 候选实验，9 项新增测试、完整 117 项通过。实验依赖只在 `.ocr-env`，核心与单元测试仍只用标准库；环境/模型/缓存不提交。实际识别结果 review_required/3：误检可被阈值过滤，但真实符号也会被漏掉；不接入自动消息处理，不能把 OCR 当作稳定身份/消息 ID。详见 docs/OCR_CANDIDATE.md。

- v0.1.4 新增 `ocr-check`，只生成内存虚构图片。108 项测试通过；本机 OCR 可运行但部分样例识别失败，必须保留 recognition_mismatch/3，不能声称真实接入通过。另一次真实 MSAA 探测被自动审批拒绝，未执行、未重试，不能推定结果。详见 docs/OCR_CHECK.md。

- 需求以 CODEX_TASK.md 与用户本轮范围为准。离线核心、UIA 结构诊断、v0.1.3 回调队列与 offline-check 已完成；用户已确认第二个号和测试好友窗口准备好，授权只读实测。此前 4.1.15.50 仅暴露基础控件的记录见 docs/LIVE_UIA_CHECK.md，当前状态以上节 v0.1.7 为准。仅当前唯一测试窗口授权读取，不采集其他会话；项目真实发送保持禁用，不接管登录。
- Python >=3.11，核心与测试只用标准库。测试：`python scripts/test.py`。
- Windows 可用 `scripts/windows.ps1 -Action test`；无 py 时自动发现实际 Python，也支持 -Python。v0.1.1 已在本机 Windows 离线验证，真实微信仍未接入。
- 适配器、模型、记忆分离；运行时模型没有工具、shell、文件或配置修改权限。
- `real_send=false` 为硬性边界；核心仍拒绝真实适配器与真实发送配置。独立 probe-wechat 可读版本与控件结构计数，不读取正文、昵称或未经验证的身份 ID，不加载配置/SQLite/模型。
- 不记录聊天正文、联系人昵称、密钥或外部异常正文。数据和备份不可提交。
- 记忆删除必须清除会话上下文与摘要，并写独立的遗忘账本；恢复不得覆盖账本。
- 先写测试并记录预期失败，再实现、验证。证据见 docs/evidence/ 和 docs/STATUS.md。
- Windows、真实微信、真实模型未实测时必须标为未验证，不以 mock 结果替代。
- 在 implementation 分支内开发。用户 2026-10-01 已授权按阶段提交并上传指定 GitHub 仓库；完成验证后常规 commit/push 无需重复询问。首次目标仓库需明确，不覆盖其他项目，不强制推送。
- 接入方案只考虑免费路线，不购买或激活 Plus。交付以 GitHub 更新为准，不再生成修订 ZIP。详见 docs/FREE_ROUTE.md 和 docs/REPOSITORY_WORKFLOW.md。
