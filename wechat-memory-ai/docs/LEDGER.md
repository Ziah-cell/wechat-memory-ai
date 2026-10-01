# 开发记录 — docs/PLAN.md

## GitHub 阶段交付方式变更

- 用户明确选择免费接入方案，并授权每完成阶段直接更新其 GitHub，不再生成新的修订 ZIP。
- 只读核对 GitHub 已登录账号 Ziah-cell，本项目没有 remote；现有 jiayu/git-text 均未绑定本项目。向用户提供目标选择后，按默认独立私有仓库 wechat-memory-ai 准备首次阶段上传，不覆盖其他仓库。
- 新增仓库入口 README、根忽略规则、阶段更新约定和免费候选证据；原产品代码不变。
- Windows 阶段提交前完整 74/74（18.225 秒）。上传候选 80 个文件，禁传路径检查与常见凭据模式检查无命中；配置/数据/日志/备份/构建包被忽略。

## 2026-10-01 Windows 续开发（v0.1.1）

- 已读取用户提供的状态/测试报告/原任务书，校验已有解压目录与原 ZIP 一致；桌面原件保留。
- Ruling: 使用现有独立工作区的 implementation 分支；仓库尚无提交，不额外创建工作树。原 ZIP 是只读基线；本地修改可与其逐文件比较。
- Windows baseline 67/69；缺失 py 的脚本另行失败。原巨大时间戳回归因默认中文编码在下一条正常输入处退出；慢 HTTP 因 stdin 等待线程与 Windows multiprocessing spawn 组合不能启动。
- CLI UTF-8 回归最初是超时 error，明确不称为业务断言 RED；修复后同一测试通过。
- Ruling: 使用显式标准管道的 subprocess 工作者替代 multiprocessing，网络仍在可终止进程内。通信线程只做管道 I/O，凭据不放命令行。代价是修改了跨平台工作进程实现，因此已完整重跑 HTTP 契约/取消测试并验证安装包；v0.1.1 Linux 尚未重跑。
- 初修 73/73；独立审查员实际执行 12 项聚焦测试，复现损坏 venv 导致 PS5.1 提前退出的问题。
- Final: fixed PS5.1 probe stderr abort — test_broken_venv_falls_back_to_working_python RED→GREEN；完整 74/74。
- Final review: 无 Critical；唯一 Important 已修复；无 Minor；Declined to judge 为空。
- 9 步隔离模拟记忆验收通过；自动解释器诊断通过；compileall 通过；离线 wheel + 隔离安装 + 安装后本地 HTTP 通过。
- 已实查微信文件版本 4.1.15.13，无运行进程；免费 wxauto4 文档仅明确 4.1.8.107。未自动降级/安装/登录/发送，不将旧注册表残留视为可用版本。
- 保留本地项目供用户继续；未合并/推送/创建远程仓库。本次交付新的 v0.1.1 Windows ZIP，原始 v0.1.0 ZIP 不覆盖。

## v0.1.0 历史记录

- 用户本轮已经明确授权实现与测试，直接执行；不添加设计批准环节。
- 全新目录无已有 Git/程序，创建独立 implementation 分支；不需要从用户既有分支分出 worktree。
- 接口检查：Config 供 Engine/CLI 使用；Store 同时供 Memory/Engine/Backup 使用；Model 和 Adapter 只经 Engine 调用。所有运行写操作在同一实例锁下执行。
- 本轮不安装 wxauto/OpenClaw；不会把候选 SDK 方法写成已验证接入。
- Task 1 complete: 6 configuration tests passed (02-config-green.txt); initial RED was missing config implementation, not a behavioral assertion.
- Task 2 complete: 23 cumulative tests passed (04-memory-green.txt); preferences, privacy replay and guarded restore verified.
- Task 3 complete: 51 cumulative tests passed (06-engine-green.txt); all HTTP traffic went only to loopback fake servers.
- Task 4 implementation: 61 cumulative tests passed (11-runtime-green.txt). The first runtime suite found a startup race: status probes momentarily owned the lock. Added a deterministic competing-process regression (10-lock-race-red.txt), then bounded startup lock acquisition to 0.5 seconds; status probes remain nonblocking.
- Remaining delivery work: documentation, independent review, final report, package extraction verification and file delivery.
- Independent review (read-only) independently ran 61/61 tests, found four Important issues: clock rollback, invalid backup initialization, huge timestamp overflow, and socket-only HTTP timeout; plus manifest-type handling.
- Final fixes: test_review_regressions.py first reproduced failures (12-review-red.txt), then durable logical clock, pre-initialization backup validation/checksum, bounded event schema and cancellable total-deadline subprocess HTTP were implemented. Whole suite: 67/67 (13-review-green.txt).
- Review decisions: Windows/real WeChat/real models remain explicitly unverified; simultaneous manual rollback of content and guard remains an explicit limitation requiring a separately retained latest guard. Malformed manifest handling was fixed as part of the same backup integrity defect.
- Final delivery validation: full suite 69/69; compileall and git diff --check passed. Wheel built offline and installed in an isolated target; installed package diagnose confirmed mock/fake/no real sending.
- Package verification: extracted candidate ZIP into a fresh directory and ran 69/69 tests again (17-archive-unittest.txt). All 23 code/script/test files match original SHA-256 values. Final repack adds documentation/evidence only and verifies every manifest entry plus ZIP CRC.
- Delivery choice follows the user's explicit request: keep the local implementation branch and provide a complete ZIP plus status/test reports; no merge, public repository, push or deployment.
