# Windows 测试结果（当前 v0.1.5）

执行日期：2026-10-01（Asia/Shanghai）。Windows 11 家庭版中文版 build 26200，Python 3.12.14，SQLite 3.53.1；PowerShell 5.1 和 7.6.5。

## v0.1.5 独立只读连接

最终完整回归 **130/130，32.715 秒，0 失败/错误/跳过**，见 [77](evidence/77-live-read-final-suite.txt)。新增 13 项覆盖首次基线、重复文字、重启不回放、窗口/进程/列表绑定、条目变化拒绝、空列表初始化、私有管道传递绑定、异常脱敏、原生编译/清理与双 PowerShell 入口。前一轮完整回归 130/130、33.658 秒见 [72](evidence/72-live-read-full-suite.txt)。

独立审查发现读取正文前绑定校验、空列表加载历史及临时目录异常脱敏问题；修复后又补齐编译器属性检查的权限错误脱敏。已先补失败回归再修复，全部发现经审查复验关闭。证据 [70](evidence/70-live-read-review-red.txt)、[71](evidence/71-live-read-review-fixed.txt)、[75](evidence/75-live-read-stat-red.txt)、[76](evidence/76-live-read-stat-fixed.txt)。

实际微信 4.1.15.50 的测试窗口已经可读，原生程序取得 8 个列表项、5 个文本项，连续 3 次绑定读取成功，初始内容没有转为新观察：[69](evidence/69-live-read-initial.json)、[73](evidence/73-live-read-bound-snapshots.json)。**尚未收到所请求的两条验证消息**；发送方方向、消息到达/历史边界、真实切换/重启、真实发送仍未验收。未调用模型、写入记忆或保存真实聊天到仓库。

v0.1.5 wheel 临时构建/安装后原生源码存在、编译成功、缺失客户端正确拒绝：[74](evidence/74-live-read-package.json)。完整运行和局限见 [LIVE_READ.md](LIVE_READ.md)。

## 独立 OCR 候选阶段（核心仍 v0.1.4）

完整回归 **117/117，28.766 秒，0 失败/错误/跳过**，见 [62](evidence/62-ocr-candidate-regression.txt)。新增 9 项标准库测试覆盖重复行、不确定符号、非法分数、报告脱敏/一致性、字面参数、真实子进程超时与 SDK 预过滤关闭。

独立审查提出两项问题：SDK 默认过滤会隐藏部分低分识别项；报告可能在没有过滤时同时声称原始失败、过滤后成功。先补失败回归 [60](evidence/60-ocr-candidate-review-red.txt)，修复后 9 项通过 [61](evidence/61-ocr-candidate-review-fixed.txt)，审查复验已关闭两项问题。

实际候选推理另用 `.ocr-env` 实测，依赖/三个模型哈希核验通过；5 张固定虚构图中深色与空白无需核查，浅色、大字号与真实符号仍需核查。最终 **review_required / 3**，见 [63](evidence/63-ocr-candidate-final.json)。没有真实微信消息读取或发送。候选依赖不加入核心；源码树实验不打包进应用 wheel，详见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。

## v0.1.4 本地 OCR 可行性诊断

完整回归 **108/108，27.490 秒，0 失败/错误/跳过**，见 [54](evidence/54-ocr-stage-regression.txt)。新增 11 项覆盖固定虚构位图的真实系统 OCR、空白图不通过、结果脱敏、实际超时和双 PowerShell 配置隔离。独立审查无待修复发现。

本机中文引擎可运行，但识别准确性检查为 **recognition_mismatch / 3**：深色通过，浅色中文/字母数字和大字号字母数字失败。报告保留失败结果；不能把程序测试通过改写为 OCR 准确性或微信兼容通过。[实际结果](evidence/53-ocr-local-result.txt)、[临时构建安装](evidence/55-ocr-package.json)。先失败、设计修正、范围和来源详见 [OCR_CHECK.md](OCR_CHECK.md)。本轮没有读取真实聊天或发送。

## 登录后只读检查阶段（代码仍 v0.1.3）

用户确认准备后，真实客户端文件为 4.1.15.50，路径匹配 5 个进程。主窗口在前台且未最小化；同一客户端的两个可见顶层窗口各仅 8 个基础 UIA 控件，无列表/文本控件证据，身份/监听未通过。原始脱敏证据为 [45](evidence/45-wechat-live-structure-probe.txt)、[46](evidence/46-wechat-window-metadata.json)、[47](evidence/47-wechat-owned-window-structures.json)，完整说明见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。

重新运行 `.\scripts\windows.ps1 -Action test`：**97/97，24.192 秒，0 失败/错误/跳过**，见 [48-live-probe-stage-regression.txt](evidence/48-live-probe-stage-regression.txt)。这仅确认原有代码回归通过，不能把真实 UIA 控件不足的结果改写为微信兼容通过。本轮没有产品代码改动、真实聊天读取、窗口动作、真实发送或真实模型调用。

## v0.1.3 独立开发阶段

执行 `.\scripts\windows.ps1 -Action test`：**97/97，23.931 秒，0 失败/错误/跳过**。原始输出：[43-offline-stage-full-suite.txt](evidence/43-offline-stage-full-suite.txt)。已有 84 项全部保持通过，新增 12 项回调/演练用例和 1 项双 PowerShell 入口用例。

新增验证覆盖并发生产、单线程消费、先入先出/相同文本不合并、暂停/断线/切换的订阅撤销、消费不跨代次、容量上限、关闭终态、异常脱敏、SQLite 重开去重和临时目录清理。Windows 入口在故意无效的个人配置旁运行成功，原文件不变；不会读取该配置或外部模型设置。

先失败证据：[38 缺失模块](evidence/38-callback-inbox-red.txt)、[40 消费跨订阅代次](evidence/40-callback-generation-red.txt)、[41 入口未实现](evidence/41-offline-check-entry-red.txt)。通过证据：[39 回调定向测试](evidence/39-callback-inbox-targeted.txt)、[42 一键演练](evidence/42-offline-check.txt)、[44 临时构建安装后演练](evidence/44-offline-stage-package.json)。

独立审查未发现需修复问题，另行通过消费期间暂停/关闭、临时资源已打开后异常清理检查。**本阶段未交互真实微信。** 97 项是离线/虚构窗口测试，不能替代真实身份、消息来源或 UI 兼容验收。

## v0.1.2 免费只读诊断阶段

执行 `.\scripts\windows.ps1 -Action test`：**84/84，22.594 秒，0 失败/错误/跳过**。完整原始输出：[36-wechat-probe-full-suite.txt](evidence/36-wechat-probe-full-suite.txt)。74 项已有核心回归保持通过；新增 10 项诊断测试。

| 检查 | 结果与证据 |
|---|---|
| 测试先行 | 缺少 wechat_probe 模块导致预期失败：[32](evidence/32-wechat-probe-red.txt) |
| 诊断新增 10 项 | 全通过：[33](evidence/33-wechat-probe-targeted.txt)；含属性脱敏、坏 JSON/错误/超时、禁用发送/身份标志、实际 WinForms UIA、路径限定、节点/深度上限 |
| 初次临时窗口测试 | no_window 失败：[35](evidence/35-wechat-fixture-initial-failure.txt)；原因是测试窗口隐藏任务栏，修正该测试设置后通过，产品范围未放宽 |
| 实际微信前提 | 4.1.15.13，not_running，0 进程：[34](evidence/34-wechat-native-probe.txt)；退出码 3，不能宣称已验证 UI 树 |
| 发行包核验 | `pywechat127 1.9.8` wheel/sdist SHA-256 均与 PyPI 一致；未安装或执行：[31](evidence/31-pywechat127-package-audit.json) |
| 本项目构建安装 | 0.1.2 wheel 含两个 PS1 资源；临时隔离安装后模块正确返回 client_not_found：[37](evidence/37-wechat-probe-package.json) |
| 独立审查 | 无需修复的发现；审查者另行通过 10 项测试、wheel 资源与 diff 检查 |

虚构 Windows 测试窗口不代表真实微信。登录/身份/真实监听、消息边界、去重、自身过滤、重名/窗口切换、锁屏/最小化/RDP、真实模型均未验证。没有真实发送测试。

## v0.1.1 基线历史结果

GitHub 阶段提交前复验：**74/74，18.225 秒，0 失败/错误/跳过**，见 [30-github-stage-unittest.txt](evidence/30-github-stage-unittest.txt)。此轮只补充免费路线和仓库交付约定，没有修改产品代码。

## 完整测试

实际执行修复后的自动解释器入口：

```powershell
.\scripts\windows.ps1 -Action test
```

**Ran 74 tests in 18.763s — OK。74 通过，0 失败、0 错误、0 跳过。**

原 69 项全部通过；新增 1 项 CLI UTF-8 回归、4 项 PowerShell 实际执行回归。PowerShell 用例分别在 5.1 和 7 执行，包括不存在的显式解释器、损坏虚拟环境回退、配置保留与错误码传播。

完整输出：[26-windows-final-unittest.txt](evidence/26-windows-final-unittest.txt)。

## 修订包验证

新 ZIP 已在独立临时目录解压运行完整测试：**74/74，18.760 秒，退出码 0**。见 [28-windows-archive-unittest.txt](evidence/28-windows-archive-unittest.txt)。最终封装只补入文档/证据；所有源码、脚本和测试与解压实测版本逐字节一致。ZIP CRC 与 manifest 的全部 SHA-256 再次校验。源码、脚本与文档的差异空白检查通过；原始失败日志保留工具输出中的空白。

## 失败与修复证据

| 阶段 | 结果与证据 |
|---|---|
| 原包首次 Windows 实测 | 67/69；巨大时间戳后正常中文消息退出码 4；慢 HTTP 未到达服务器。[18-windows-baseline.txt](evidence/18-windows-baseline.txt) |
| 原 PowerShell 脚本 | 找不到 py，退出码 1。[19-windows-launcher-baseline.txt](evidence/19-windows-launcher-baseline.txt) |
| 新脚本回归 RED | 3 测试，4 个子用例失败（两个 Shell）；无效解释器拒绝原本已通过。[20-windows-scripts-red.txt](evidence/20-windows-scripts-red.txt) |
| 强制 ASCII 默认编码 RED | CLI 读取线程退出后挂起，测试等待超时（1 error，非业务断言失败）。[21-windows-utf8-red.txt](evidence/21-windows-utf8-red.txt) |
| 初次修复 GREEN | 73/73，通过。[22-windows-green.txt](evidence/22-windows-green.txt) |
| 独立审查回归 RED | PowerShell 5.1 对损坏 venv 的 stderr 提前终止；1 失败。[25-windows-review-red.txt](evidence/25-windows-review-red.txt) |
| 审查修复 GREEN | 最终 74/74，通过。[26-windows-final-unittest.txt](evidence/26-windows-final-unittest.txt) |

独立审查还验证了管道写线程被阻塞时，取消/总时限能够终止工作进程并回收管道；无 Critical、无遗留 Minor。审查记录见 [REVIEW.md](REVIEW.md)。

## 其他实际验证

- 9 步临时数据模拟验收全部断言通过：[23-windows-acceptance.json](evidence/23-windows-acceptance.json)。覆盖称呼重启保留、纠正、遗忘和恢复旧内容备份后不复活。
- 不带 -Python 的脚本自动发现本机解释器，默认诊断通过：[24-windows-auto-diagnose.txt](evidence/24-windows-auto-diagnose.txt)。
- `python -X utf8 -m compileall -q src scripts tests`：退出码 0。
- `pip wheel --no-deps --no-build-isolation --no-index`：v0.1.1 wheel 离线构建成功；`pip install --no-index --no-deps --target <临时目录>` 成功，未改全局环境。
- 安装后的包诊断与本地回环 HTTP 调用各成功；模型只收到一条虚构输入：[27-windows-installed-smoke.json](evidence/27-windows-installed-smoke.json)。

真实微信和外部模型均未验证。下面保留的是 **v0.1.0 的 Linux 历史证据**，不代表修改后的 v0.1.1 重新在 Linux 跑过。

---

# v0.1.0 Linux 历史测试结果

执行日期：2026-10-01（Asia/Shanghai）。执行环境：Linux、Python 3.12.14、SQLite 3.53.1。

## 自动化测试

实际执行：

```bash
python3 scripts/test.py
```

最终输出：**Ran 69 tests in 6.990s — OK**。69 项通过，0 失败、0 错误、0 跳过。

| 测试模块 | 数量 | 覆盖内容 |
|---|---:|---|
| test_config | 6 | 默认离线、配置类型/未知字段/范围、网络显式开启、凭据不进入 repr、URL 限制 |
| test_engine | 21 | 中文多行、干运行、模拟收发、重启去重、合法相同文本、白名单/自身/群聊/历史、身份切换、顺序、上下文预算、额度、未知发送、注入和日志 |
| test_memory | 17 | 来源元数据、偏好持久化/更新、临时状态、敏感拒存、检索隔离、确认清空、遗忘、摘要、备份恢复/迁移 |
| test_models | 7 | 真正 HTTP 请求发往回环假服务：契约、鉴权/配额/服务失败、格式、重定向、超时、网络禁用与端口不可达 |
| test_review_regressions | 7 | 时间回拨、旧备份遗忘、损坏/空/不匹配数据库、畸形清单、巨大时间戳、慢速响应总时限与取消 |
| test_runtime | 11 | 真正子进程：单实例竞争、重启、JSONL、暂停/恢复/停止、异常退出、备份/恢复、诊断、启动竞态、真实慢速本地 HTTP 的停止 |

完整逐项输出：[evidence/14-final-unittest.txt](evidence/14-final-unittest.txt)。机器可读记录：[evidence/test-results.json](evidence/test-results.json)。测试中的所有人物、偏好、密钥均为虚构数据。

## 其他实际验证

| 命令/操作 | 实际结果 |
|---|---|
| `python3 -m compileall -q src scripts tests` | 退出码 0 |
| `git diff --check` | 退出码 0 |
| `python3 -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir <临时目录> .` | 构建 wechat_memory_ai-0.1.0-py3-none-any.whl 成功 |
| `python3 -m pip install --no-index --no-deps --target <隔离临时目录> <wheel>` | 退出码 0；仅安装到指定临时目录，未改全局环境 |
| 从安装后的包运行 `python3 -m wechat_memory --config <示例配置> diagnose` | 退出码 0；返回 mock / fake / dry_run=true / network_enabled=false / real_wechat_verified=false |

标准库运行路线不需要 pip；构建/安装检查仅验证项目打包配置。pip 在容器以 root 运行时发出通用提示，安装目标为独立临时目录。

## 压缩包验证

已将完整项目压缩后解压到新的目录，从该目录执行 `python3 scripts/test.py`：**69 项通过，6.911 秒，退出码 0**。解压后的 23 个源码/脚本/测试文件与交付源文件的 SHA-256 全部相同。ZIP CRC 与内含 PACKAGE_MANIFEST.json 的逐文件校验通过。原始输出见 [evidence/17-archive-unittest.txt](evidence/17-archive-unittest.txt)。最终打包仅补入此验证记录等文档，程序和测试文件保持同一字节内容。

## 失败与修复证据

每个主要模块先编写测试、运行预期失败，再补实现。01/03/05/07 的最初 RED 是缺少模块的导入错误，**不将其说成已经验证了每项业务断言**。随后完整实现并运行对应行为测试。

运行控制首轮发现启动竞争，08 保留失败输出；10 的确定性竞争测试先失败，11 修复后通过。独立审查产生 12 的行为回归失败，13 修复后全部通过；14 补验结构异常恢复与真实慢速 HTTP 取消后共 69 项通过。审查详见 [REVIEW.md](REVIEW.md)。

## 未执行的验收

- Windows 解释器、msvcrt 文件锁分支、PowerShell 脚本执行。
- 普通个人微信登录/收发、真实联系人身份、窗口切换、锁屏、最小化、RDP 断开与长期稳定运行。
- 真实模型服务、实际鉴权、订阅授权或账单费用。
- wxauto/OpenClaw 安装、集成、发布版本兼容与授权许可。

因此，这份结果只能说明当前 Linux 环境的离线核心、模拟适配器、真实本地 HTTP 测试服务和子进程控制通过；**不能说明已接通真实微信或真实模型**。
