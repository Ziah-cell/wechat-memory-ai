# 项目开发约定

- 当前 v0.1.6 修复 listen-wechat 顶部移除后的连续性：旧连续后缀与新前缀至少两个 token/内容摘要锚点完全一致且有追加行时继续；其他变化停止。会话已见 token 最多 4096 个，重现或超限整批停止；首次非空快照仍只建立基线。新增 6 项回归，完整 136 项通过。见 docs/LIVE_READ.md。
- 真实固定文本收发已通过：两条相同左侧来信可见且原生读取到两项；一次明确授权的固定回复经 Computer Use 点击发送，用户确认收到。该次授权已用完，不得再发。旧有界监听器曾因顶部移除停止，没有返回新增观察；本次修复只有虚构快照回归，尚未进行修复后的真实新消息监听验收。证据 docs/evidence/78-live-exchange.json。自动 AI 回复、项目发送适配器与真实模型未启用；sender_verified/history_boundary_verified 仍 false，不接入 Engine/模型/记忆。无需重登或重做固定回复验收。

- 核心仍 v0.1.4；新增源码树独立 RapidOCR 候选实验，9 项新增测试、完整 117 项通过。实验依赖只在 `.ocr-env`，核心与单元测试仍只用标准库；环境/模型/缓存不提交。实际识别结果 review_required/3：误检可被阈值过滤，但真实符号也会被漏掉；不接入自动消息处理，不能把 OCR 当作稳定身份/消息 ID。详见 docs/OCR_CANDIDATE.md。

- v0.1.4 新增 `ocr-check`，只生成内存虚构图片。108 项测试通过；本机 OCR 可运行但部分样例识别失败，必须保留 recognition_mismatch/3，不能声称真实接入通过。另一次真实 MSAA 探测被自动审批拒绝，未执行、未重试，不能推定结果。详见 docs/OCR_CHECK.md。

- 需求以 CODEX_TASK.md 与用户本轮范围为准。离线核心、UIA 结构诊断、v0.1.3 回调队列与 offline-check 已完成；用户已确认第二个号和测试好友窗口准备好，授权只读实测。此前 4.1.15.50 仅暴露基础控件的记录见 docs/LIVE_UIA_CHECK.md，当前状态以上节 v0.1.6 为准。仅当前唯一测试窗口授权读取，不采集其他会话；项目真实发送保持禁用，不接管登录。
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
