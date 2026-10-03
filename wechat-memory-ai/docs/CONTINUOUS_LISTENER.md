# 常驻只读监听与最小化验证（v0.1.18）

目标是启动一次后持续监听，并支持微信真正最小化到任务栏。当前已有隐藏工作进程、状态查询和停止控制；新增`background`模式直接读取普通聊天窗口的文本，无需进入多选。实机在最小化状态下读取了3927次，随后因`native_reader_timeout`停止。**当前监听已停止；真实新来信、长期稳定运行和最小化自动回复尚未验收。**

## 运行

只保留已授权测试联系人的一个独立聊天窗口，保持普通聊天状态。窗口可以最小化；读取器不会恢复窗口、输入文字或抢焦点。

```powershell
.\scripts\windows.ps1 -Action start-listener -ListenerReader background -ClientPath 'D:\软件\Weixin\Weixin.exe'
.\scripts\windows.ps1 -Action listener-status
.\scripts\windows.ps1 -Action stop-listener
```

默认状态目录是`data/listener`，用`-ListenerData`指定其他目录时，启动/状态/停止须一致。本轮普通模式实测目录为`data/background-listener-20261003`，旧多选模式为`data/minimized-listener-20261003`；两者最后检查均已停止。继续前先查相应目录，不把旧状态视为当前运行状态。

源码入口为`python scripts/monitor-wechat.py --data-dir data/listener start --reader background --client-path <本机Weixin.exe路径>`。安装入口`wechat-memory-monitor`使用相同参数。`start`隐藏启动工作进程，并等待该次启动的基线状态；`status`只读固定字段；`stop`向当前代际发送本地停止指令，不按状态文件中的PID杀进程。

| 读取方式 | 窗口要求 | 新文本方向 |
| --- | --- | --- |
| `visual`（默认） | 普通聊天、不最小化 | 视觉方向候选，未验证身份 |
| `background`（显式选择） | 普通聊天，允许最小化 | 全部`unknown`，只计数 |
| `selection`（保留的实验模式） | 保持多选，允许最小化 | 名称前缀候选或`unknown`，未验证身份 |

三种方式均不读取个人配置或`.env`，不调用模型、不写聊天记忆、不发送微信消息。状态只保存固定计数、原因和本地进程控制信息。核心`dry_run`仍会调用模型和记忆，因此这里没有借用核心流程。

## 消息边界

- 首个非空视口仅作基线，不回放已有内容。循环没有固定结束秒数，也不要求每次发送随机标记；目前只统计未验证的界面出现候选。
- 窗口、进程和列表必须保持绑定；连续锚点、旧组合重现拒绝及4096组合上限保留。不自动重绑或恢复。再次启动会建立新基线，停机期间的消息不会补处理。
- 普通后台模式不读取窗口名称或像素；前后两次复核控件、类型、文本和绑定。状态或内容变化时丢弃整次读取。已绑定的`background_snapshot_changed`最多重读3次，共享原8秒预算；其他错误停止。双读不是原子快照。
- 后台文本全部保持`unknown`，只增加`filtered_unknown_texts`，不推断来信或自身；不能进入`PreflightSession`、`ReadOnlyWeChatSource`或Engine。历史同步仍可能产生候选。
- 多选旧模式按窗口显示名称前缀标记`incoming_candidate`，其他名称为`unknown`；同名或嵌套前缀会误判，不能用于身份授权。退出多选、昵称变更、绑定或连续性变化会停止。其一致性重读规则保持不变。

`minimized_observation_enabled`只表示所选模式允许最小化读取；`window_minimized`表示最后接受的快照，监听停止后不能代表当前窗口状态。`minimized_snapshots`是已接受最小化快照的累计数。`minimized_supported`、`reply_ready`继续为false，指完整后台回复未验收；身份、历史、发送、模型和记忆标志也保持false。

## 实测与剩余工作

[254](evidence/254-minimized-arrival-incomplete.json)记录旧多选监听6755次后停止。用户确认操作过聊天窗口，恢复检查可见两条测试文本，不能追认成实时捕获，也不能归因为最小化来信导致失败。[257](evidence/257-background-monitor-start.json)普通模式基线启动通过；[258](evidence/258-background-minimize-transition.json)窗口操作期间连续性丢失，随后检查仍未最小化，不能算最小化转换测试通过。

准确最小化后另起普通后台监听，[259](evidence/259-background-minimized-timeout.json)记录3927次最小化快照、0新增文本，最终读取超时停止。它证明静态文本可读，尚不能证明新消息可捕获或无人值守可靠。旧阶段的多选基线、停止/重启和视觉拒绝结果见[TEST_RESULTS.md](TEST_RESULTS.md)，失败记录全部保留。

下一阶段优先诊断超时以及窗口/视口变化后的恢复边界，再验证最小化新消息、可靠收发方向、目标身份、历史处理及后台发送。不能只加长超时、放宽绑定或把未知方向当来信。锁屏、睡眠、RDP、托盘关闭和开机自启动均未验证；没有连接模型/记忆/发送。自动回复启用前仍需用户最后确认。
