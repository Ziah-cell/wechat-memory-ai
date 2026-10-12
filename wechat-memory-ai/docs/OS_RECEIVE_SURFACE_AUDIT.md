> 已取消路线的历史报告（2026-10-12）。下文命令/下一步不再执行；研究源码、重复程序和构建产物已删除，旧哈希仅记录当时状态，不能用于核验当前工作副本。当前方案见 [WINDOW_OPEN_PLAN.md](WINDOW_OPEN_PLAN.md)。

# 替代接收来源核查：快照、ETW 与 Windows 通知

2026-10-09。本轮承接[双角色退出失败](BOUNDED_RECEIVE_FAULT_BOUNDARIES.md)，比较不持续安装目标硬件断点的来源。结论是：**尚未选出可实施的真实接收来源；三个候选都没有补齐本项目所需的消息交付与身份依据。** 这不是所有采集方法均不可能的证明，也不是三项实机测试失败。本轮只有官方接口核查与固定 DLL 磁盘只读分析，没有运行这些系统采集接口。

## 候选与决定

| 候选 | 能取得什么 | 本项目仍缺什么 | 本轮决定 |
| --- | --- | --- | --- |
| ReadProcessMemory 轮询 / PSS 快照 | 指定时刻的内存或线程上下文；PSS 的 VA_SPACE 只有区域元数据 | 已定位入口的 RDX 是瞬时参数，不是可反复读取的事件队列；尚无稳定地址、对象寿命、消息保留期或丢失检测契约 | 不用提高采样率替代事件交付证据；不在微信上抓全进程快照 |
| ETW 订阅 | 已注册提供者主动写出的事件 | 未识别兼容 .50 的消息提供者 GUID、事件号、有效负载结构和身份/历史语义 | 不启动通用或全系统跟踪来碰运气 |
| UserNotificationListener | 应用信息、通知 ID、创建时间、可视通知内容及增删通知 | 缺少通用的微信账号/好友/消息 ID、方向、历史/重连判据与完整内容保证；未验证 .50 通知能被此接口读取 | 当前不作为单独的自动回复来源，也不开启通知权限 |

上述缺口先于性能和辅助者退出试验。为一个没有有效消息来源的快照循环制作“不会留下断点”的夹具，不能证明它能接收微信来信，因此本轮没有新增原生夹具或修改旧断点清理代码。

## 接口依据与推论边界

**快照。** `PssCaptureSnapshot` 捕获一次进程状态。`PSS_CAPTURE_VA_CLONE` 涵盖所有可克隆页面；`PSS_CAPTURE_VA_SPACE` 只记录区域信息，不含页面内容。因此克隆后只读取 512 字节，也不能把采集范围说成原先批准的 512 字节入口观察。官方释放接口要求使用持有快照的进程句柄；已读文档没有给出足以满足本项目门槛的“所有辅助进程中途消失”保证。本轮未实测其故障生命周期。[捕获接口](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot)、[捕获标志](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags)、[释放接口](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot)。

“入口调用可能完全发生在两次采样之间”是基于采样语义的推论，不是本轮微信漏收实测。若以后发现有保留期和序号的持久消息缓冲，需评估那个具体来源；当前没有发现它。不能将此结论外推为所有只读内存来源都不可行。

**ETW。** 提供者需要已有事件埋点，控制器负责启停会话和启用提供者；通用控制器不会生成应用没有发布的消息字段。ETW 也有缓冲、消费速度和事件大小导致的丢失情形。故至少需要明确提供者、消息结构和丢失处理，不能把线程/磁盘/网络活动当成文字来信。[ETW 官方模型](https://learn.microsoft.com/en-us/windows/win32/etw/about-event-tracing)、[会话配置](https://learn.microsoft.com/en-us/windows/win32/etw/configuring-and-starting-an-event-tracing-session)。本轮未启动、枚举或停止系统跟踪会话，也未证明控制器退出会自动清理会话。

**通知。** 监听器需要系统中的显式用户许可。`GetNotificationsAsync` 返回当前通知，后台变化触发器要求重新同步当前列表；撤销权限后读取可能静默返回空列表。因此通知列表不是已保证完整、可重放的消息日志。[通知监听指南](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener)。

`UserNotification` 的属性为 `AppInfo`、`CreationTime`、`Id`、`Notification`。后者是带 `Visual` 和 `ExpirationTime` 的 `Notification`，不是通知发送端的 `ToastNotification` 对象；不能假定可以取得原始 launch/actions、任意标签或调用快捷回复。监听器公开方法也没有通用回复/激活方法。通知 ID 只标识通知，应用身份不能代替微信内的账号与好友身份；显示名称和正文哈希同样不足。[UserNotification](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.usernotification?view=winrt-26100)、[Notification](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.notification?view=winrt-26100)、[监听器方法](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.management.usernotificationlistener?view=winrt-26100)、[发送端 ToastNotification](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.toastnotification?view=winrt-26100)。这是所检查 API 的边界，不排除某个应用自行在可视内容中附加字段；本轮没有这种微信字段依据。

## 固定 .50 DLL 的实际结果

使用磁盘审计脚本（历史源码路径 `experiments/audit_os_receive_surfaces.py`，已删除），只读取既有批准的 `Weixin.dll`，SHA-256 为 `0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b`，大小 204099112 字节。未加载此 DLL。

- 普通导入 1 个描述符、333 个符号；延迟导入 39 个描述符、884 个符号，共 1217 个符号。
- 在预先列出的 17 个 API 名称中，只匹配 `SHELL32.dll!Shell_NotifyIconW`，IAT RVA 为 `0xbb60548`。没有匹配所列 ETW/WinRT 名称。
- 7 个固定通知/TraceLogging 子串各按 ASCII 与 UTF-16LE 检查，共 14 个检查，均未命中。它们不是 14 项采集测试。
- 另用已有 PE 解析辅助程序重读导入并复核子串结果；同一执行者核查，不是独立审查。
- 定点搜索 `FF15/FF25` 的 RIP 相对直接引用，随后从 `.pdata` 函数起点完整反汇编校验指令边界，确认该 IAT 槽的 8 处直接调用，分布于 6 个函数。没有声称覆盖间接数据流。

一个具体静态路径位于 `0x4c3c0d0..0x4c3c796`：`0x4c3c702` 写 `[rsp+0xe4]=0x90`，随后设置 `rdx=rsp+0xd0`、`ecx=1`，在 `0x4c3c71a` 调用上述 IAT。按 x64 `NOTIFYICONDATAW` 的 `uFlags` 偏移 `0x14`，对应 `NIF_INFO | NIF_SHOWTIP` 和 `NIM_MODIFY`。这说明所选代码包含请求气泡通知的路径，**不证明当下聊天执行该路径、正文完整、每条来信均触发，或 UserNotificationListener 可以接收它**。

`Shell_NotifyIconW` 操作任务栏通知区域；结构中的 `uID/guidItem` 标识图标。不能把它们解释成好友或消息 ID。官方还说明 Windows 11 的该类气泡横幅在超时/消失后不会留在通知中心，不能依赖稍后列表轮询恢复这些内容。本轮未读取本机通知或更改设置。[Shell_NotifyIconW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw)、[NOTIFYICONDATAW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-notifyicondataw)。

导入/子串未命中不证明不存在动态解析、其他模块、其他编码或未检查接口。普通导入与延迟导入均已覆盖，但这不是全客户端提供者发现。命中一个系统通知函数也不足以建立接收方案。

## 后续工作只接受具体来源

原硬件断点方案的双角色退出失败仍有效；不增加守护层，不把更短等待、手工清槽或通知外观当作修复。三个 OS 候选本轮收敛，不重复无新增依据的扫描或模拟计数。

恢复实施前，需要出现以下至少一个具体的新依据：带消息语义的兼容 ETW 提供者；具有已知寿命、序号和丢失规则的只读缓冲；或明确提出另一种接入机制及其安装、并发、全部辅助者退出和卸载设计。进程内 Hook/注入不是本轮选定方案，也不在既有外部断点观察的实机授权范围内，不能因用户说“继续”而静默切换。若研究这种不同机制，先完成静态方案与自建夹具范围，再另行确定实机范围。

此前 UIA、固定数据库候选及 Web/Bot 路线的结论保持，见[UIA 源码核查](SOURCE_ROUTE_AUDIT.md)、[数据库核查](DB_COLLECTOR_FEASIBILITY.md)、[非 UIA 路线](NON_UIA_ROUTE_AUDIT.md)。接收可行性不等于目标绑定发送已经解决。

## 核查与保存

[507 接口比较](evidence/507-os-receive-contracts.json)、[508 固定磁盘结果](evidence/508-os-receive-disk-audit.json)、[509 核查与检查点](evidence/509-os-receive-checkpoint.json)保存范围与哈希。旧 29 份研究源码、29 份产品源码、24 份旧分析脚本及 323 份旧证据保持。新增脚本 1 份，产品仍 0.1.22，自动回复关闭，监听保存停止。本轮未运行产品或原生夹具测试；原生退出失败没有被重新标记成通过。
