# 常驻只读监听与最小化验证（v0.1.17）

目标是启动一次后持续监听，并支持微信真正最小化到任务栏。当前已经实现隐藏工作进程、状态查询和停止控制；新增多选标签读取模式在本机微信4.1.15.50最小化时能持续建立/保持基线。**最小化自动回复尚未完成**。后台新来信验收另行记录，不能用静态控件可读代替。

## 运行

只保留已授权测试联系人的一个独立聊天窗口。多选模式须先在该窗口的一条消息菜单中选择“多选”；保持多选状态后可以最小化。它没有可用输入框，本模块也不会退出多选或发送。

```powershell
.\scripts\windows.ps1 -Action start-listener -ListenerReader selection -ClientPath 'D:\软件\Weixin\Weixin.exe'
.\scripts\windows.ps1 -Action listener-status
.\scripts\windows.ps1 -Action stop-listener
```

默认状态目录是`data/listener`，用`-ListenerData`指定其他目录时，启动/状态/停止须一致。本轮实测使用`data/minimized-listener-20261003`。先查这个目录的状态，避免重复启动或把旧已停止监听当作仍在运行。

源码入口也可运行`python scripts/monitor-wechat.py --data-dir data/listener start --reader selection --client-path <本机Weixin.exe路径>`。安装后的入口为`wechat-memory-monitor`，参数相同。`start`隐藏启动工作进程并等到该次启动的基线状态；`status`只读固定字段，`stop`向当前代际发送本地停止指令，不按状态文件中的PID杀进程。启动成功不等于来信或自动回复验收成功。

省略`-ListenerReader selection`使用原视觉候选模式，仍要求不最小化。两种模式均不读取个人配置或`.env`，不调用模型，不写聊天记忆，不发送微信消息；状态只保存固定计数、原因和本地进程控制信息。`dry_run`核心会调用模型和记忆，因此这里没有借用核心的dry_run。

## 消息边界

- 启动后的首个非空视口仅作基线，不回放已有内容。持续循环没有固定结束秒数，也不要求每次发送随机标记；它只统计未验证的界面出现候选。
- 同一窗口/进程/列表绑定不变，原连续锚点、旧组合重现拒绝和4096组合上限保留。不自动重绑、断线重连或补发积压；停止后再次启动建立新基线，停机期间来信不会补处理。
- 多选模式只读取消息标签，前后两次复核控件、类型、文本和窗口绑定，不截屏、不恢复窗口、不抢焦点。窗口状态在读取中变化时丢弃整次结果。已有绑定下仅`selection_snapshot_changed`可在同一8秒预算内最多读取3次，其他错误立即停止。
- 标签以窗口显示名称加空格开头时标记为`incoming_candidate`；其他标签保持`unknown`，**不把其他名称一概当作自身**。同名或名称前缀嵌套可能误判，因此这不是身份验证。非文本行用于连续性，不生成文本候选。
- 昵称变更、退出多选、窗口替换或连续性丢失会停止。多选标签快照不能进入原视觉`PreflightSession`/`ReadOnlyWeChatSource`。历史同步仍可能产生候选，不能直接转成Engine事件。

`minimized_observation_enabled=true`表示选择了该读取方式；`window_minimized`与`minimized_snapshots`反映已接受快照。`minimized_supported`和`reply_ready`继续为false，指完整最小化自动回复未验收；`sender_verified`、`history_boundary_verified`、`real_send_supported`、`model_called`、`memory_written`均为false。

## 实测与剩余工作

普通视觉模式的隐藏启动、状态、停止已经在237通过；最小化时原模式按233拒绝。230仅证明最小化时布局元数据仍存在，不证明正文或新消息。新增多选模式首次最小化切换在241触发前后变化并停止；保留失败，随后加入有界重读。244/246证明已最小化窗口的持续基线读取与停止/重启零回放，仍不代表实时新消息到达。

多选读取方式来自正常UI探索；参照上游[多选入口说明](https://github.com/Hello-Mr-Crab/pywechat/blob/main/src/pyweixin/WeChatTools.py)和[监听说明](https://github.com/Hello-Mr-Crab/pywechat/blob/main/src/pyweixin/WeChatAuto.py)独立实现，没有安装、导入或分发其软件包，也没有采用其“不是对方即为自己”的判断。免费路线不包含客户端注入、数据库密钥提取或解密。

还需验证真实最小化新来信、最小化切换恢复、可靠自身/目标身份、历史边界、退出/重启以及后台发送方式。当前多选窗口隐藏了输入框，不能由可读取推断可后台发送。锁屏、睡眠、RDP、托盘关闭和开机自启动均不在已验证范围。自动回复启用前仍需完成模型/记忆桥接与发送前复核，并取得用户最后确认。
