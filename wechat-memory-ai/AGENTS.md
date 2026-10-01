# 项目开发约定

- v0.1.4 新增 `ocr-check`，只生成内存虚构图片。108 项测试通过；本机 OCR 可运行但部分样例识别失败，必须保留 recognition_mismatch/3，不能声称真实接入通过。另一次真实 MSAA 探测被自动审批拒绝，未执行、未重试，不能推定结果。详见 docs/OCR_CHECK.md。

- 需求以 CODEX_TASK.md 与用户本轮范围为准。离线核心、UIA 结构诊断、v0.1.3 回调队列与 offline-check 已完成；用户现已确认第二个号和测试好友窗口准备好，授权只读实测。当前 4.1.15.50 的两个可见窗口各仅暴露 8 个基础控件，真实身份/消息监听尚未验证，详见 docs/LIVE_UIA_CHECK.md。禁止真实发送，不接管登录。
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
