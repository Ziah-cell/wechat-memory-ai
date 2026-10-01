# 项目状态：Windows 离线核心已验证，真实微信仍未接入

更新日期：2026-10-01（Asia/Shanghai）。当前版本：**0.1.1**。

用户最新决定：**先做免费版本，阶段完成后直接提交并上传 GitHub，后续在同一仓库更新；不再提供下载修订包流程。** 免费接入候选与下一阶段边界见 [FREE_ROUTE.md](FREE_ROUTE.md)，交付约定见 [REPOSITORY_WORKFLOW.md](REPOSITORY_WORKFLOW.md)。以下 ZIP 记录仅是已完成的历史验证。

GitHub 阶段基线目标：私有仓库 `Ziah-cell/wechat-memory-ai`，分支 `implementation`。上传前重新运行 74 项测试全部通过（18.225 秒），证据为 `evidence/30-github-stage-unittest.txt`；Git 忽略本地数据、凭据和历史交付包。

## 本次续开发结果

在用户 Windows 工作区继续开发；已校验已有解压目录与原 ZIP 的 60 个文件完全一致，原 manifest 59 项 SHA-256 一致，ZIP CRC 正常。原桌面 ZIP、STATUS.md、TEST_RESULTS.md 未修改。

环境：Windows 11 家庭版中文版 / build 26200 / 64 位；Python 3.12.14；SQLite 3.53.1；PowerShell 5.1 和 7.6.5。本机没有 py 启动器；使用已存在的 Codex 缓存 Python，没有安装或升级系统软件。

**最终 74 项自动化测试通过，0 失败、0 错误、0 跳过。** 原版在本机是 67/69，两个失败已经修复；详见 [TEST_RESULTS.md](TEST_RESULTS.md)。

## 本次修改

- CLI 在读取线程启动前统一标准流 UTF-8，修复默认 Windows 编码下中文输入导致中断/挂起的问题；新增中文与 emoji 回归。
- HTTP 工作者使用显式私有标准管道的独立 subprocess，修复 stdin 线程持续等待时 Windows multiprocessing 工作者无法正常启动的问题。网络请求仍可因停止/超时被终止；请求凭据不进入命令行或日志。
- PowerShell 脚本支持 `-Python`、`WECHAT_MEMORY_PYTHON`、项目虚拟环境、实际 PATH 解释器及本机 Codex 缓存运行时；忽略 WindowsApps 占位入口。诊断脚本传递配置和退出码，已有配置不覆盖。
- 独立审查发现 PowerShell 5.1 遇到损坏虚拟环境时会因 stderr 提前退出；新增真实损坏环境回归，修复后可继续寻找可用 Python。

## 实际完成的验证

- 完整 74 项 Windows 测试，包括 msvcrt 锁竞争、异常退出后的锁释放、暂停/恢复/停止、慢 HTTP 中止、中文与去重、记忆/遗忘/恢复。
- PowerShell 5.1/7 实际调用、显式 Python、无效 Python 拒绝、损坏环境回退、配置不覆盖、诊断错误码。
- 独立的 9 步临时数据模拟验收：记住称呼、重启、纠正、查看、备份、遗忘、重启、恢复旧备份后不复活。使用虚构“小禾/阿禾”，没有写入用户正式记忆。
- 源码编译；离线 wheel 构建；隔离目录安装；安装后诊断和安装后本地 HTTP 调用。
- 修订 ZIP 独立解压后再次 74/74，通过；最终程序/脚本/测试字节与已测试包一致，CRC/manifest 校验完成。
- 默认启动脚本自动找到本机 Python，诊断结果为 mock / fake / dry_run=true / network_enabled=false / real_send_supported=false。

## 真实微信接入的当前阻塞

实查 `D:\软件\Weixin\Weixin.exe` 文件与产品版本均为 **4.1.15.13**；检查时未发现微信进程。注册表的旧 3.9.12.51 记录指向文件不存在，不能当成可用旧客户端。

重新读取的一手安装文档只声明免费 wxauto4 支持到 **4.1.8.107**，公共仓库仍显示停止更新。当前没有证据证明该免费候选适配本机 4.1.15.13。Plus 版也尚未核实该精确版本。来源与边界见 [COMPATIBILITY.md](COMPATIBILITY.md)。

真实适配器、登录、联系人稳定身份、真实收发、真实模型、锁屏/最小化/RDP、24 小时稳定运行、自启动均未完成或未验证。没有购买、激活或安装候选适配器，没有自动登录或发送微信。

## 如何运行与下一步

在项目目录执行：

```powershell
.\scripts\windows.ps1 -Action diagnose
.\scripts\windows.ps1 -Action run
```

需要时用 `-Python 'C:\实际目录\python.exe'` 指定 Python 3.11+。当前解释器来自 Codex 缓存，适合本次验证；长期部署可另行选择独立 Python 安装。

免费路线已确定。下一阶段优先核验 pyweixin 的正常 UI 自动化可行性；由用户本人登录受控的第二个普通个人号后，先验证 UI 可访问性与唯一测试联系人的稳定身份，再开发只读/dry-run 接入。发送固定测试文本前仍需明确收件人和一次发送授权。当前没有取得真实客户端接入成功的证据。

数据与备份仍为本机明文；真实发送硬边界保持关闭。详见 [DATA_AND_PRIVACY.md](DATA_AND_PRIVACY.md)。
