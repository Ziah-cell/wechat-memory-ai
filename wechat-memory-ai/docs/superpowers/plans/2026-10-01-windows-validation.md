# Windows 实测与修复 Implementation Plan

> **For agentic workers:** 使用 superpowers:executing-plans 逐项完成；用户已要求了解交接后继续，本轮在现有独立工作目录进行可逆修复与验证。

**Goal:** 在本机 Windows 跑通离线核心、中文输入、HTTP 测试子进程与 PowerShell 入口。

**Architecture:** 保持 mock / fake 默认值与真实发送禁用。CLI 统一 UTF-8；HTTP 请求继续在可终止的独立进程内执行，用显式标准管道避免 Windows 等待 stdin 时阻塞 multiprocessing spawn。

**Tech Stack:** Python 3.11+ 标准库，PowerShell，SQLite，unittest。

**Spec:** CODEX_TASK.md、docs/WINDOWS_NEXT.md，以及本次实际 Windows 失败证据。

## Global Constraints

- 不安装/降级微信，不自动发送，不配置自启动，不读聊天库或真实密钥。
- 原桌面 ZIP 和交接文件保留；修改限于工作区项目。
- 测试与模型 HTTP 请求仅使用虚构输入和回环服务。
- 测试先失败再修复；Windows 结果与先前 Linux 结果分别记录。

## Review Focus

- 未开启 Python UTF-8 模式的中文管道输入（任务 1）。
- stdin 持续等待时 HTTP 请求必须到达本地服务器（任务 2）。
- 停止/超时要终止请求进程，不能等待网络响应（任务 2）。
- Python 路径含空格、无 py 启动器、无效显式路径（任务 3）。
- 启动脚本保留已有配置，错误退出码传给调用方（任务 3）。

## Task 1: CLI UTF-8

Files: src/wechat_memory/cli.py、tests/test_runtime.py。

- [x] 新增强制外部 ASCII 默认编码时中文/emoji 正确往返的子进程测试；记录失败。
- [x] 在 CLI 入口、启动读取线程之前设置标准流 UTF-8；不依赖调用者的 -X 参数。
- [x] 运行新测试和原巨大时间戳回归，均须通过。

## Task 2: 可取消 HTTP 子进程

Files: src/wechat_memory/models.py、tests/test_runtime.py、tests/test_models.py。

- [x] 原 test_stop_cancels_an_actual_slow_http_call 在 Windows 失败；独立复现表明后台 stdin 读取与 multiprocessing spawn 组合阻塞启动。
- [x] 替换为显式 stdin/stdout/stderr 的 subprocess 工作者；请求与凭据经私有管道，不进入命令行；I/O 线程负责 communicate，主线程持续检查取消与总时限。
- [x] 保持完整模型错误映射、无重试、返回长度与进程回收行为。
- [x] 原慢 HTTP 停止回归和完整 HTTP 契约测试通过。

## Task 3: PowerShell 与交付

Files: scripts/windows.ps1、scripts/diagnose-windows.ps1、tests/test_windows_scripts.py、README.md、docs/STATUS.md、docs/TEST_RESULTS.md、docs/COMPATIBILITY.md、docs/WINDOWS_NEXT.md。

- [x] 写实际 PowerShell 子进程测试：显式 Python、配置不覆盖、错误码传递、无效解释器拒绝。
- [x] 增加 -Python 参数/WECHAT_MEMORY_PYTHON、可用解释器发现、Python 3.11+ 验证，避开 WindowsApps 占位命令；诊断脚本传参并保留退出码。
- [x] Windows PowerShell 5.1 与 PowerShell 7 执行入口；跑完整测试、编译检查、模拟记忆验收。
- [x] 更新状态与一手兼容性证据，校验后生成新的 Windows 修订包，不替换原始包。

## 执行记录

- ZIP CRC 正常，60 个文件与已有解压目录一致，原 manifest 的 59 项 SHA-256 全部匹配。
- Windows 11 家庭版中文，build 26200；Python 3.12.14 / SQLite 3.53.1；PowerShell 7.6.5。
- 原始 Windows 套件 69 项：67 通过、2 失败，见 evidence/18-windows-baseline.txt。原 launcher 找不到 py，见 evidence/19-windows-launcher-baseline.txt。
- Ruling: 在已有独立的新项目工作区使用 implementation 分支；仓库尚无提交，无法从历史创建工作树，原 ZIP 提供完整基线。

- 完成：最终 74/74（18.763 秒）；独立审查唯一 Important 已经通过回归修复；无遗留 Minor。
- 封装验证完成：独立目录解压后 74/74（18.760 秒），最终封装仅补入文档与证据；程序/脚本/测试字节与已测试 ZIP 保持一致。
