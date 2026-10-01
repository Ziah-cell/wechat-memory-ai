# v0.1.6 微信独立只读连接

2026-10-01，用户本人完成登录后，实际微信 4.1.15.50 的独立测试私聊窗口能提供消息控件。Computer Use 和项目独立程序均读取成功。初次窗口有 8 个列表项、5 个文本项；原生程序连续 3 次读取并保持同一绑定，没有把已有文字输出为新增观察。证据：[69](evidence/69-live-read-initial.json)、[73](evidence/73-live-read-bound-snapshots.json)。

随后已完成一次真实双向固定文本验收：两条相同来信显示为两个独立左侧气泡，原生读取器也读到两个文本项；用户明确授权的一条固定回复通过 Computer Use 点击一次发送，观察到唯一右侧绿色回复、输入框清空，用户确认收到。该次授权已用完。测试文字核对仅忽略用户省去的空格，不改写真实文本或合并相同文本。脱敏证据：[78](evidence/78-live-exchange.json)。没有调用真实模型、启用自动回复或开发项目发送适配器。

旧有界监听器在 8 行变 9 行、保留旧列表末尾 6 行并追加时间行与两条文本时停止，**没有返回新增观察**。v0.1.6 针对此变化修复 Python 状态机，使用虚构快照回归；本阶段未再次读取或操作真实微信，修复后的真实新消息连续监听尚未验收。

## 运行

保持第二个普通号已登录，只打开一个测试好友的独立聊天窗口，进入 `wechat-memory-ai` 目录：

```powershell
.\scripts\windows.ps1 -Action listen-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe' -ListenSeconds 30
```

时长可设 1–300 秒；Ctrl+C 停止。首次建立基线，之后每秒尝试读取一次；系统 UIA 单次调用可能使实际间隔变长。编译最多 25 秒，每次读取最多 8 秒，异常即停止。源码入口是 `scripts/listen-wechat.py`，安装后的命令为 `wechat-memory-listen --client-path ... --seconds 30`。

`status=reading` 与 `window_bound=true` 表示当前窗口已绑定；`observed_new_rows/texts` 是相对于基线新增的 UI 列表项/文本项计数。初始化时列表为空则保持 `initializing`，首批非空行只建立基线。正常结束退出码 0，读取失败或中止为 3；退出码 0 不表示真实收发验收通过。

不使用 `config.toml`、API Key 或 OCR 环境，不调用模型、不写入记忆。默认输出没有聊天正文或联系人信息。核心的 `run` 仍为控制台模拟器；这条独立连接没有隐藏的发送开关。

## 读取范围与连续性

- 使用已有系统 .NET Framework x64 编译器临时编译项目自己的 `live_reader.cs`，不安装软件包，结束清理临时程序。缺少编译器时停止。
- 按完整客户端路径限定进程，仅接受唯一的 `ChatSingleWindowwxid_…` 独立私聊窗口。窗口标题或昵称不参与选择；不自动搜索其他联系人。
- 绑定进程、进程启动时间、窗口、窗口 AutomationId 和列表实例。后续绑定通过私有 stdin 传给原生提供器，在读取消息正文之前检查；读取之后再检查窗口/列表。不会因旧窗口消失而读取新窗口的正文。
- 最多遍历 1024 个控件、深度 48、列表 256 项、每项 10000 字符。只读取限定窗口内列表项的正文，不打开聊天记录、不滚动、不点击或输入。
- 完整前缀保留时接受追加；顶部旧行移出时，只有旧快照的连续后缀与新快照前缀按 token 和内容摘要完全一致、至少保留两个锚点且有追加行才继续。仅移除无追加、单锚点、无重叠、内部移除/重排/内容变化或列表重建均停止。
- 会话内保留所有已见 token（包括基线和非文本行），最多 4096 个。已移出的 token 不得再次作为新增项，即使正文改变；超限或重现时整批停止，不增加本批计数、不返回部分结果。达到上限后不变快照仍可读取，下一批新 token 到达才停止；不会自动重建基线或恢复。
- 两条相同文字保留为两个条目。本地观察编号是一次读取会话的 UUID 和序号，**不是微信消息 ID**。重新启动时重新建立基线，不回放当前可见记录，也不承诺恢复停机期间消息。

真实正文只在受控子进程管道和进程内存中用于读取与比较，不写入报告、截图文件、数据库或仓库。旧行只保留令牌与内容摘要用于比较，不把内容摘要当成消息身份。

## 已知限制

RuntimeId 只用于同一运行中 UI 实例的比较，可能被复用；AutomationId 也不是跨所有窗口/版本的全局身份保证。[Microsoft RuntimeId 说明](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.getruntimeid)、[AutomationId 说明](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.automationidproperty)。

采样间发生又恢复的变化可能不可见；初始非空列表后续仍可能追加同步的历史记录。因此“新增观察”不等于已证明的新到达微信消息，`history_boundary_verified=false`。发送方方向未取得可靠证据，`sender_verified=false`；当前不会把任何观察自动交给模型、记忆或发送器。

两条相同来信和一次固定回复的人工实机验收已通过，但目视左右方向不等于程序已具备可靠的发送方识别。修复后的连续监听、历史边界、自身过滤、另一联系人切换、跨重启、锁屏/最小化/RDP 和长期稳定性仍待实测。此前不能读取 UI 的原因没有确定，不把本次成功推广到其他账号/版本。

## 验证

v0.1.6 新增 6 项回归，覆盖顶部移除后两条相同文本、锚点/追加要求、旧 token 重现（含正文变化及完整前缀追加）、4096 上限与批次原子性、重启不回放。实现前 19 项、6 errors（其中一个测试有两个失败子例）：[79](evidence/79-live-overlap-red.txt)。实现后 19/19、1.875 秒：[80](evidence/80-live-overlap-targeted.txt)；完整 136/136、30.124 秒、0 失败/错误/跳过：[81](evidence/81-live-overlap-full-suite.txt)。这些是虚构数据回归，不代替修复后的真实新消息监听验收。

版本更新后通过 Windows 项目入口最终复验：`scripts/windows.ps1 -Action test -Python <现有解释器>`，136/136、30.488 秒、0 失败/错误/跳过：[82](evidence/82-live-overlap-final-suite.txt)。

独立只读审查无待修复发现，另行定向测试和内存边界检查通过：[83](evidence/83-live-overlap-review.json)。

以下为 v0.1.5 验证记录：

新增 13 项测试：基线、相同文本、重新启动、绑定变化、已有行变化、空列表后历史加载、正文读取前传递绑定、异常脱敏、超时参数、实际原生编译及临时清理、双 PowerShell 入口与配置隔离。

实现前缺失模块：[65](evidence/65-live-read-red.txt)。测试数据构造错误及修正：[66](evidence/66-live-read-targeted.txt)、[67](evidence/67-live-read-targeted-fixed.txt)。独立审查发现并修复读取前绑定、空列表初始化及文件系统异常脱敏，失败/修复证据：[70](evidence/70-live-read-review-red.txt)、[71](evidence/71-live-read-review-fixed.txt)、[75](evidence/75-live-read-stat-red.txt)、[76](evidence/76-live-read-stat-fixed.txt)。全部审查发现已复验关闭。

完整测试结果见 [TEST_RESULTS.md](TEST_RESULTS.md)。v0.1.5 wheel 已临时构建安装，确认包含原生源码、安装后能编译并拒绝不存在的客户端：[74](evidence/74-live-read-package.json)。该安装验证没有访问真实微信。
