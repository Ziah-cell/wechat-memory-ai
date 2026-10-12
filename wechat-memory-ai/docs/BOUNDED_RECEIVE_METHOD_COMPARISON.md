> 已取消路线的历史报告（2026-10-12）。下文命令/下一步不再执行；研究源码、重复程序和构建产物已删除，旧哈希仅记录当时状态，不能用于核验当前工作副本。当前方案见 [WINDOW_OPEN_PLAN.md](WINDOW_OPEN_PLAN.md)。

# 三种退出恢复办法的自建程序比较

2026-10-09。用户要求“继续，尝试多种办法”。延续[475授权](evidence/475-bounded-receive-authorization.json)，本轮实际实现并比较三种实验办法；所有附加、寄存器操作和故意终止都限于本项目创建的子进程。**独立调试进程改善了前端退出的恢复，但三种办法都未通过调试进程自身强制退出的完整要求，仍不进入微信。**

## 实测对照

| 办法 | 正向结果 | 仍失败的情况 | 判断 |
| --- | --- | --- | --- |
| DbgEng 一次性硬件断点 | 首次命中后再结束观察器，3次恢复；首次命中后连续调用期间结束，3次恢复 | 首次命中前结束，3次均单步异常退出；先遇到非标记消息后，后来的标记不再被捕获 | 缩短断点驻留时间，不能覆盖等待首条消息的故障窗口；重新安装断点会重新进入该窗口 |
| 前端与持有调试连接的进程分离 | 修正清理竞态后，空闲时前端退出3次恢复；连续自主调用期间前端退出9次恢复 | 结束真正持有断点的调试进程，3次均单步异常退出 | 仅改善前端故障隔离，不能把调试进程改称服务就免除其退出检查 |
| Windows 原生调试 API，绕过 DbgEng | 正常分离和重复命中恢复通过 | 首次命中前、已命中后、连续调用期间结束调试进程，各3次均单步异常退出 | 在本机该原生实现中也存在残留，不能只归因于 DbgEng 封装 |

[482](evidence/482-bounded-receive-method-comparison.json)记录选定30次对照：15次恢复、15次未恢复，命令失败如实保留。另有6次修正后连续调用复验及2次一次性断点功能对照，分别记录在483和482；不能合并成“全部通过”。之前失败版本和一次中途终止的测试批次也保留，没有用最终结果覆盖。

## 对照怎样避免假通过

夹具新增两个仅用于自建程序的命令：`ping` 在主线程实际处理后返回 pong，排除 armed 前积压的心跳；`burst` 自主连续执行同一虚构消息函数一秒，每次调用后间隔约1毫秒。测试脚本在第一次调用已经返回、后续调用仍在进行时结束指定子进程。目标不等待清理完成，也不捕获单步异常。成功还要求连续调用结束、再次调用成功以及后续心跳增长。

两种角色分别标记为 controller 和 debugger_owner。结束 controller 时，独立调试进程通过自己的存活检测请求原事件循环取消、移除断点和分离；结束 debugger_owner 时，没有将另一个活着的进程或一次心跳当成恢复证明。所有子进程最终均由其创建者回收，测试没有选择或操作用户应用。

首次命中前的测试均先取得 arming 之后的 pong，目标确已恢复执行；它不同于上一轮 armed 后立刻结束时残留暂停计数的场景。失败后的闲置线程快照仍显示 DR0 指向夹具函数、DR7=0x401、TF=0。原生 API 对照仅安装主线程的一个执行槽，恢复自己的断点时使用 RF；没有加载 DbgEng、修改函数正文或注入自定义 DLL，也没有实现消息采集或新线程覆盖，不能称为可替换适配器。

## 独立调试进程中发现并修正的正常清理竞态

初版直接沿用旧 Engine，前端在连续调用期间退出的3次中有2次使目标单步异常退出。清理日志显示，上一轮 WaitForEvent 曾成功，但清理开始时执行状态已经为 GO；旧状态仍被当作可直接清理的停止点。

第一次修正只在请求 GO 后撤销旧停止点标记，仍有2次清理在再次请求 GO 时失败，不能宣布修复。随后实验子类同时避免在已经 GO 时重复提交 GO，并要求重新取得实际停止事件后再移除断点。该版空闲前端退出3次、连续调用前端退出3次通过，再针对新发现的竞态复验6次，均分离成功并继续自主调用；9次连续调用样本各完成641–657次函数执行。样本结果不能证明所有调度次序都已覆盖。

这个修正保留在实验 FreshStopEngine（历史源码路径 `experiments/receive_probe_variants.py`，已删除），没有改写原观察器（历史源码路径 `experiments/receive_probe_observer.py`，已删除）或将原失败测试改成预期失败。它修正的是存活调试进程的正常清理路径；自身被强制结束时仍不会执行这段路径。[483](evidence/483-bounded-receive-broker-cleanup.json)区分每次尝试、修正后样本和未解决故障。

## 一次性断点的功能代价

首次调用就是标记时，可以捕获且正常分离，来源仍为 unknown。首次调用为非标记消息、第二次才是标记时，目标两次调用都完成，但观察器只记录一次命中、没有标记记录。这不是解析失败，而是断点已按一次性语义删除。不能将这种漏采当作“安全接收成功”，也不能假定微信入口的第一次调用必然来自测试好友。

## 依据、范围和继续条件

微软文档说明[一次性断点首次命中即删除](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/controlling-breakpoint-flags-and-parameters)，[SetExecutionStatus 请求执行、下一次 WaitForEvent 才驱动执行](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol-setexecutionstatus)，以及 [SetInterrupt(EXIT) 不保证目标暂停](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol-setinterrupt)。原生事件结构对照[固定 minwinbase.h](https://github.com/microsoft/win32metadata/blob/76c04c2021ef4a831a6f1e06d9566002d746139b/generation/WinSDK/RecompiledIdlHeaders/um/minwinbase.h)，继续异常规则依据 [ContinueDebugEvent](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-continuedebugevent)；RF 用途依据 [Intel 系统编程手册](https://cdrdv2-public.intel.com/858456/253669-088-sdm-vol-3b.pdf)。文档解释机制，表中结论来自本机自建程序实测。

[484核查](evidence/484-bounded-receive-method-validation.json)绑定所有运行版本和缓存哈希。未重跑产品回归、原完整12项原生测试或17项离线投影；29份产品源码、24份旧研究脚本及298份先前证据保持。新增的均是研究脚本；原观察器和原失败测试保持不变。

已有授权有效，当前障碍仍是技术条件。后续可以保留独立调试进程及其正常清理修正，但进入微信前仍须提出并证明真正持有断点的进程硬退出时的恢复机制，不能只演示前端退出。若没有这样的机制，应比较不持续设置目标调试寄存器的具体采集来源；不再仅换进程名称、缩短等待或放宽退出门槛。尚未验证本机微信兼容性、消息方向/新旧、最小化发送或自动回复。

[485检查点](evidence/485-bounded-receive-method-checkpoint.json)：产品0.1.22、自动回复关闭、旧监听保存停止状态；没有微信附加/内存读取、窗口操作、密钥/聊天数据库访问、真实发送或Jev调用。没有遗留测试进程。一次性断点和原生调试均为实验对照，未替换为软件断点或自定义注入。
