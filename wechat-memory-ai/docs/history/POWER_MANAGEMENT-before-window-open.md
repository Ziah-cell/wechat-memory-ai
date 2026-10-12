> 2026-10-12 历史归档。旧最小化命令/运行状态已失效，当前方案见 [计划](../WINDOW_OPEN_PLAN.md)。

# 监听与系统待机（v0.1.21）

微信窗口最小化与电脑待机是两种状态。最小化可以继续读取；进入系统待机后，桌面程序可能被暂停，不能保证继续监听。

## 这次故障的证据

[284](../evidence/284-standby-timeout.json)保存旧v0.1.19监听的停止状态与脱敏电源事件：2266次快照全部最小化，没有新增文本；第2267次调用触发子进程超时。外层耗时1806710ms，原生最后检查点为completed/2791ms。Windows事件506进入待机、507退出待机相隔1804219ms；退出事件比停止状态文件早2932ms。

这些证据表明本次调用跨过约30分钟待机，不能将全部外层耗时解释为UIA持续阻塞。原生检查点与系统事件使用不同时间基准，不能据此断言原生输出在待机前已完成，也不能确定父进程通信/超时的具体竞态。259旧超时没有相同事件证据，原因仍未知。

当时未收到用户发送确认或睡眠操作确认。没有新增不等于没有来信，也不能判定最小化来信测试失败。旧会话已经停止；显式新启动只建立新基线，不补处理停机期间已可见内容。

## 可选防自动待机

启动时显式添加开关；默认关闭：

```powershell
.\scripts\windows.ps1 -Action start-listener -ListenerReader background -KeepAwake -ClientPath '<本机Weixin.exe路径>'
```

Python和安装入口的对应参数为`start --keep-awake`（直接运行工作进程时为`run --keep-awake`）。已有监听不会被热更新；须先正常停止，再使用所需开关显式启动。启动/状态/停止应使用相同的`-ListenerData`目录。

请求仅在监听线程运行期间存在。通过`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`申请，退出时恢复该线程之前的执行状态；不修改电源计划，不额外要求屏幕常亮或away mode。初始化失败在读取微信前以`keep_awake_failed`停止；释放失败也停止，原有读取错误优先保留，工作线程结束后其请求随之结束。[Microsoft API说明](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate)

此请求不能阻止用户手动睡眠、合盖或按电源键。Modern Standby与电池策略还可能限制请求持续时间，因此不能保证电脑始终清醒，更不能宣称睡眠中也能监听；持续清醒会增加耗电。[Microsoft Modern Standby说明](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/prepare-software-for-modern-standby)

状态字段：

| 字段 | 含义 |
| --- | --- |
| `keep_awake_requested` | 本代监听启动时是否显式选择开关；旧状态为false |
| `keep_awake_request_active` | 上次发布时已成功申请且未成功释放，并且工作进程仍活动；仅表示请求生命周期，不保证操作系统继续执行程序 |

进程退出后第二项始终为false。状态不写API异常原文、系统电源计划、用户名或聊天内容。8秒读取预算、绑定复核、未知方向、首基线跳过及失败停止规则没有改变；没有新增自动重启、重绑或回复。
