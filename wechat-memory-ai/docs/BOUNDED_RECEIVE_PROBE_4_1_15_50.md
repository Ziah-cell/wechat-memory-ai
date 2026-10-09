# 4.1.15.50 有界接收观察：待授权方案

2026-10-09。目标仍是普通个人号、单测试好友、真正任务栏最小化、长期记忆自动回复。本页提出下一次**可行性实验**，不是已实现的采集器，也不启用自动回复。

## 本轮决定

停止重复审查没有更新的候选和扩展通用偏移。今日 GitHub API 复核：mosheng20205/WechatHook4.1.10.27 仍为 `713ec7d6f01d858e067a623c9bf2cda64d0d3e19`，aixed/WeChat-Hook 仍为 `e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6`，均与此前固定审查相同；前者仍限定 4.1.10.27，后者不能以保留回调配置证明已有接收链。此次检索没有找到可据以接入本机 .50 的新实现，不推断全网不存在。[原接收候选](https://github.com/mosheng20205/WechatHook4.1.10.27/tree/713ec7d6f01d858e067a623c9bf2cda64d0d3e19)、[原发送候选](https://github.com/aixed/WeChat-Hook/tree/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6)、[472复核](evidence/472-bounded-receive-proposal-basis.json)。

建议用外部调试器在固定版本的**一个消息转换入口**观察一次受控来信。它先回答两个有限问题：该入口在真实最小化时是否接收到本次专用标记；外部观察器能否按预算退出并让被观察程序继续运行。它不回答所有初始同步/重连消息的新旧分类，不确认服务器 ID 唯一性，不证明后台发送可用。

## 具体采集方法

- 独立 x64 观察进程，使用 Windows 自带 DbgEng。此次只检查到 `C:\Windows\System32\dbgeng.dll` 和 `dbghelp.dll` 文件存在，尚未加载，也未确认完整运行兼容性。依赖不可用即停止，不自动安装或下载其他调试器。
- 固定 DLL 磁盘 SHA256 为 `0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b`，大小 204099112。未来连接时必须按用户选择的 PID、进程创建身份、模块完整路径与构建核对；多个候选或模块变更即停止，不遍历附加。
- 在模块基址加 RVA `0xa773b0` 设置唯一的处理器执行断点，采用 `AddBreakpoint(DEBUG_BREAKPOINT_DATA)`、`SetDataParameters(1, DEBUG_BREAK_EXECUTE)` 和明确的地址。命中时只取入口 RDX 作为源对象候选，不执行微信内部函数、不申请发送对象、不注册内部服务回调。入口 `0xa773d7: mov rsi, rdx` 与字段链已重新核对，详见472。
- 这是 **invasive 调试附加**：要控制执行并在断点时暂停线程，不能称为 Windows 的 noninvasive 模式或“对进程完全无影响”。工程代码不注入自定义 DLL、不使用软件断点修改微信函数正文；调试引擎自身的附加/中断机制仍属于运行干预。先在自建夹具验证附加事件和处理器断点行为，不默认它一定适合微信。
- 外部进程在暂停期间读取限定字段，把必要值复制到自己的有限缓冲区；不把目标地址/借用指针留给异步消费者。每次继续执行后丢弃目标指针，下次从当次 RDX 重新开始。无有效指针、短读或布局不符就结束实验，不尝试其他偏移。

Microsoft 文档明确区分[非侵入调试的限制](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/noninvasive-debugging--user-mode-)、[附加与 WaitForEvent](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugclient2-attachprocess)、[处理器断点类型](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol-addbreakpoint)和[执行访问参数](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/controlling-breakpoint-flags-and-parameters)。这些是 API 契约，不是本机成功运行证据。

## 读取与记录上限

就绪后才生成本次随机标记：ASCII `VXPROBE:` 加 32 个随机十六进制字符，共 40 字节。用户届时从原定测试好友发送一次；现在不要求发送，也不沿用308的旧输入。使用独立随机 HMAC 会话密钥，标记和密钥都不写证据或聊天记忆。Python 离线实验中的常量是虚构测试数据，不能用于实机。

| 顺序 | 暂时读取的字段 | 筛选与输出 |
| --- | --- | --- |
| 1 | RDX 开始的 0x58 字节源对象头 | raw+14 的类型必须为1；其他类型只计数，不解引用字符串 |
| 2 | raw+20 → nested+8 → 字符串描述符 | 长度不等于40就跳过，不读取正文载荷；长度必须不大于容量 |
| 3 | 描述符的40字节正文 | 只做完整标记比较，不做前缀/模糊匹配；不匹配立即丢弃，不读取端点 |
| 4 | 仅匹配后：raw+8、raw+18 的嵌套字符串，各最多128字节；raw+50 的8字节数值 | 记录端点 A/B 的会话 HMAC、field12 的不同域 HMAC及其是否非零；不命名为已认证 wxid/server_id |

字符串布局投影为描述符+10长度、+18容量；容量15时内联，容量至少16时取首指针。限定 x64 低半区地址、完整长度返回、最多512字节/12次读取；不做任意地址搜索、全内存转储或字符串扫描。未匹配消息仍可能暂时读到其对象头、字符串描述符及**恰好40字节的其他正文**，因此不能承诺读取前就只接触测试好友。未匹配数据不落盘、不上传、不进模型；这部分暴露必须包含在授权范围内。

DbgEng 的读取返回成功也可能是短读，必须同时核对实际字节数；实际实现优先用不缓存的读取并检查 HRESULT 与长度。[读取契约](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugdataspaces-readvirtual)。内存中的 Python/运行库副本可能无法保证立即物理清零，因此这里只承诺不主动持久化原文，不能承诺安全擦除所有副本。

落盘白名单：随机会话号、相对毫秒、观察序号、模块哈希、入口RVA、标记匹配布尔、上述 HMAC、数值是否非零、读取字节/调用数、当前窗口是否最小化、固定错误码和退出阶段。`direction=unknown`、`origin=unknown` 固定保留；没有 `verified` 或自动准入开关。每次实验换密钥，标签不能跨实验用于稳定识别账号。

## 最小化、期限与退出

1. 只在用户所选窗口与 PID 对应、当前 `IsIconic` 为 true 时开始；不恢复窗口、不抓图、不重新启动旧 UIA 监听。就绪、每次命中、结束前分别核对，任何非最小化/未知则停止。离散观测不能宣称覆盖每一毫秒。
2. 附加准备预算10秒；进入观察后最多120秒或200次入口命中或1次完整标记匹配，先到者结束。这是实验目标上限，不是 Win32 调用必然在此时间内完成的保证。
3. 事件线程 `WaitForEvent` 使用250毫秒等待片段并在每次返回后检查截止时间；回调不得阻塞日志/网络或重入等待。单次停顿超过100毫秒或累计停顿超过1秒就请求清理。阈值是保守实验政策，不是已验收性能。
4. 正常清理为移除本次唯一断点、调用 `DetachProcesses`、核对返回及自建夹具的恢复心跳，然后释放观察器资源。不得用杀死微信、重启微信或结束调试目标来代替退出。
5. 超时/取消由独立控制线程请求 `SetInterrupt(DEBUG_INTERRUPT_EXIT)` 唤醒事件循环。它不保证目标已暂停，不能当作清理完成；需要事件线程执行移除/分离。发生清理错误必须报告 `cleanup_unknown`，保留控制进程供恢复，不强杀观察器，不把 timeout 标为正常结束。
6. 调试器异常退出是否影响目标、处理器断点是否覆盖新线程、未处理异常如何透传、取消时的恢复行为，必须先用自建程序验证。任何一项失败都不连接微信。不能保证受保护客户端允许附加或不会受停顿影响。

[等待限制](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol-waitforevent)、[中断不等于暂停](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol-setinterrupt)、[删除断点](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/setting-breakpoints)、[分离后恢复线程](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugclient-detachprocesses)。这些 API 返回须在实现中检查，不以文档代替验证。

## 实施前后分别怎样判定

当前已完成的只有[离线布局投影](experiments/check_receive_probe_layout.py)：17项虚构字节案例通过，覆盖内联/堆字符串、恰好匹配、短读/畸形布局、读取预算和输出脱敏。最大双端点案例504字节/10次读取；未调用 Windows 调试 API、未创建被调试夹具、未访问微信进程。记录见[473](evidence/473-bounded-receive-offline-validation.json)。

获批后实施顺序：先编写独立观察器和自建原生夹具，验证普通/新线程命中、延迟事件、取消、目标退出、布局错误、满预算、正常分离、观察器异常结束后的目标存活与恢复心跳；保存实际 API 结果。只有上述验证通过才进入一次微信实验。夹具成功不证明微信兼容，微信拒绝附加/入口不命中就如实结束，不降级、不改补丁或扩大扫描。

微信实验成功的严格范围是：本次随机标记完整匹配、有限字段读取成功、命中时对应窗口最小化、观察器正常分离，且未出现已观测异常。入口收到对象不等于数据库提交或最终展示；初始同步、重连补拉、其他设备同步、自发消息、账号切换和方向仍未认证。现阶段即使成功也只能输出研究记录，不能连接 Engine、模型、长期记忆或发送。

后续若继续开发采集器，必须单独解决同源账号/目标和方向、新旧与重连边界、去重及后台发送结果。当前方案没有把 nonce 规则推广为普通来信规则，也没有把 debugger 当长期运行适配器。

## 本次需要决定的范围

建议授权**进入这一有界调试观察阶段**：允许实现并在本项目自建程序上验证观察器；验证通过后，允许对用户选定的 .50 微信进程进行一次上述附加、处理器断点、有限内存读取和最小化状态核对。允许读取范围以本页表格为限，不含密钥、聊天数据库、其他进程、任意内存转储或发送。用户现在无需提供账号ID或聊天内容。

目前该权限尚未取得。项目[AGENTS.md](../AGENTS.md)原授权是“允许只读公开文档/源码”，并明确“不等于安装、账号接入、提取本机密钥、注入/改写客户端或发送授权”；[既有观察约定](ISOLATED_OBSERVATION_4_1_15_50.md)也要求先给出“具体采集方法、字段、范围与退出方式”。因此当前继续研究的授权不能自行扩展为调试附加或进程内存访问。产品保持0.1.22、自动回复关闭，检查点见[474](evidence/474-bounded-receive-proposal-checkpoint.json)。
