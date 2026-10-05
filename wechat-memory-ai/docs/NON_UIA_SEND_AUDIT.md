# 非 UIA 扩展核查：发送证据与消息边界

后续343–348已完成[本机.50磁盘静态对照](SEND_COMPATIBILITY_4_1_15_50.md)：固定了EXE/DLL的精确哈希与版本，旧9个函数调用RVA均在新模块异常表区间内部；找到发送协议字符串，但尚无可调用入口。下一项转为固定模块的离线反汇编/调用关系核查。下文“本轮未读取本机模块”仅描述本报告最初的公开源码阶段，不覆盖这次后续磁盘读取。

2026-10-05（北京时间），接续 [331 的固定源码核查](NON_UIA_ROUTE_AUDIT.md)和 [338 的本次 Web 不可用反馈](evidence/338-web-login-user-result.json)。本轮新增 5 个仓库、46 份固定公开文本，未重复扫码，未安装、导入、编译或执行候选。完整清单见 [339](evidence/339-non-uia-expansion-manifest.json)。产品仍 v0.1.22。

**本轮仍没有可准入的本机 Windows 微信 4.1.15.50 全程最小化双向来源。** 新的实质证据是：两个 4.x Hook 确有内部发送代码，但版本不匹配，且返回值、接收事件或重放契约不足；更接近 4.1.15 的 easyChat 实现仍依赖界面焦点。以下“无需窗口输入”仅描述所查代码，不是实机最小化通过，也不表示系统待机时可工作。

## 固定候选与决定

| 新核查来源 | 精确版本依据 | 接收 / 发送路径 | 身份、恢复与发送结果 | 决定 |
| --- | --- | --- | --- | --- |
| aixed/WeChat-Hook @ e905d07a | README 指定 4.1.10.27；内部调用使用固定偏移和对象布局 | 所查初始化/路由未建立消息接收回调证据；发送直接调用 Weixin.dll | 接收参数保留不等于有接收事件；HTTP success 不检查 native 结果 | 不准入；不能以项目标题“收发”补全双向能力 |
| navysoto/wxhook @ fbccd527 | README 与 WeixinOffsets.cs 均限定 4.1.11.52 | 进程内断点取消息；共享内存命令触发内部发送 | 有 MsgId/From/Wxid/Timestamp，但自身绑定、历史边界、去重、满队列和超时关联有缺口 | 作为 4.x 调用链研究材料；不在 .50 上试注入 |
| lich0821/WeChatFerry @ 0f5c60a0 | native 的 SUPPORT_VERSION 是 3.9.12.51 | 内部函数收发及 RPC | 有源 ID/方向字段；取出队列后再编码/发送，失败未补回；文本 status=0 不是回执 | 修正“仅 .17”的笼统印象；仍非本机 4.x 来源 |
| ttttupup/wxhelper @ fa90a0ea | README 最高列到 3.9.5.81，所查代码固定偏移 | 内部函数发送与消息 Hook | 同步事件有 from/to/msgId/createTime；发送封装调用后固定 success=1 | 3.x 架构参考，不外推到 .50 |
| LTEnjoy/easyChat @ 70f6f412 | 新增实现文件 wechat_4_1_15_8.py，不是 .50 证据 | UIA、全局热键、焦点、剪贴板、Enter | 按名称查找对象；返回 True 只说明操作路径返回 | 快速排除，未做与任务无关的全面 UIA 复审 |

本轮公开检索包含精确的 4.1.15.50、4.1.15 Hook 与最小化发送组合；未取得精确匹配的完整来源。搜索结果不穷尽全部项目，也不能证明不存在私有或未被索引的实现。没有采购、联系作者或访问受限 wx.qq.com。

## 1. aixed：发送不靠输入框，但 success 没有送达含义

[版本声明](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/README.md#L26-L33)与[末尾兼容说明](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/README.md#L310-L314)都限定 4.1.10.27。[SendText](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/wx_send.cpp#L473-L498)构造目标和消息对象后直接调用 base + offset；[构造器](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/wx_send.cpp#L409-L426)写入目标与正文。这里未见恢复窗口或键鼠操作，但偏移、结构大小和调用上下文没有 .50 依据，不能只替换版本字符串。

[HTTP 路由](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/SendTextMsg.cpp#L28-L38)调用返回 void 的 SendText 后固定写 ret=0 / success，既不回传源消息 ID，也没有对端回执关联。因此不能把 HTTP 200、ret=0 或无异常映射为本项目的“已送达”。

接收不能从名称推断：[README 参数表](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/README.md#L91-L103)明确只保留 RecvType 和回调地址的解析；所查 [Evt_WeixinLoad](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/inline_weixin_dll_load.cpp#L167-L212)、[路由注册](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/http_routes.cpp#L9-L16)没有给出可审阅的入站消息事件路径。本轮不宣称仓库所有历史提交或其他交付物都没有接收能力。

启动也不是被动读库：[初始化](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/src/inline_weixin_dll_load.cpp#L145-L203)会调用 Patch_Revoke，修改客户端内存，并启动监听 0.0.0.0 的服务。这些默认行为超出本轮静态权限；没有执行。

## 2. navysoto：较新的 4.x 收发示例，仍缺完整契约

[README](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/README.md#L1-L4)和[偏移表](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/WeixinOffsets.cs#L3-L35)明确是 4.1.11.52。它不是通用 4.1.x 自动适配器。[NativeEntry](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/NativeEntry.cs#L24-L43)等待模块出现后安装收发 Hook 并启动共享内存服务，没有在这里核验文件版本/哈希，且未检查两个初始化返回值。因此 PING 成功也不能说明收发 Hook 均安装成功。

**发送：** [SendText](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/MsgSendHook.cs#L68-L94)最多等待 15 秒捕获协程线程，再入队、挂硬件断点、等待 30 秒；不直接操作输入框。代码依赖 GetCoroCtx 安全点被触发，失败信息甚至保留“点一下触发”的提示，见 [ShmServer](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/ShmServer.cs#L99-L132)。这不证明所有发送必须点击，也不能证明真正最小化且空闲时能自行完成。

[CallDoSend](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/native/seh_bridge.c#L77-L80)丢弃客户端内部返回值，只把没有捕获到异常视为调用成功；[调用链末尾](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/native/seh_bridge.c#L164-L175)据此返回 1。它证明的是内部调用返回，不是服务端接受或对端收到。

超时也不能自动重试：

- [UI 会话](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Shared/WxHookSession.cs#L95-L104)等待共享内存 35 秒，但 native 路径可能用到 15 + 30 秒。客户端 [Invoke](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Shared/ShmClient.cs#L137-L161)超时只抛错并释放本地锁，没有撤销请求或请求 ID。
- [Seh_Wait](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/native/seh_bridge.c#L280-L289)超时会清 pending，不能误写成“完全没有取消”。但 [DrainThunk](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/native/seh_bridge.c#L422-L431)可能已取走请求并进入调用，清 pending 不证明未发送；外层 35 秒超时也不等于已经执行了内层清理。
- 共享内存名称固定，协议没有账号/进程代次或请求关联号；[协议字段](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/ShmServer.cs#L11-L45)与 [Invoke](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Shared/ShmClient.cs#L137-L161)不足以排除重连或超时后的旧完成信号被下一请求读取。此为静态时序风险，未声称实机复现。

**接收：** [数据结构](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/MsgRecvHook.cs#L8-L17)有 MsgId、From、Wxid、Timestamp，但不包含经绑定的自身账号、显式 unknown 方向或历史标志。字段名字不能直接认证其在 .50 的语义。[会话重连后立即 POP](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Shared/WxHookSession.cs#L39-L76)，没有启动基线/历史隔离契约。

[捕获规则](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/MsgRecvHook.cs#L140-L175)另有三个静态反例，详见 [340](evidence/340-hook-static-traces.json)：

1. 非零 ID 只比较上一条，A、B、A 可再次入队；不是持久去重。
2. ID 为零时比较 type 和最多前 64 字节正文的指纹，不含对方身份。连续相同正文或相同前缀的合法消息可能被合并，不能作为本项目准入策略。
3. 128 槽环形缓冲按模数写入，没有检查未消费槽是否将被覆盖；消费者 [ProcessPending](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/MsgRecvHook.cs#L204-L228)按 readIdx 读取。129 条尚未消费的捕获足以覆盖首槽，不能据累计计数证明完整接收。

这些均为规则/控制流推演，没有执行该项目。ID 的零值、方向不明、队列溢出及重连积压仍须停止或隔离，不能靠本地 UUID、当前时间、正文摘要补造真实事件。

## 3. WeChatFerry 与 wxhelper：补齐 native 证据，仍不是 .50 候选

前次引用的 Node 客户端指南要求 3.9.12.17；本次检查的是另一仓库的 native 固定提交，其 [SUPPORT_VERSION](https://github.com/lich0821/WeChatFerry/blob/0f5c60a034fcac234cabd000b49c9200defa7f7d/WeChatFerry/spy/spy.h#L7-L10)已为 **3.9.12.51**。两份资料的对象不同，不能笼统说“所有 WeChatFerry 只到 .17”，也不能将 .51 当作 4.x 兼容。

WeChatFerry [收取消息](https://github.com/lich0821/WeChatFerry/blob/0f5c60a034fcac234cabd000b49c9200defa7f7d/WeChatFerry/spy/message_handler.cpp#L24-L65)按偏移获取 ID、is_self、时间和会话；这些比 UIA 丰富，但仍须在适配版本实测身份与历史语义。[RPC 先 pop 再编码/发送](https://github.com/lich0821/WeChatFerry/blob/0f5c60a034fcac234cabd000b49c9200defa7f7d/WeChatFerry/spy/rpc_server.cpp#L154-L200)，编码失败 continue，发送失败只记日志，所查路径没有回队或持久确认。它不保证中断后完整交付，也没有本项目要求的重连积压边界。

[文本内部调用](https://github.com/lich0821/WeChatFerry/blob/0f5c60a034fcac234cabd000b49c9200defa7f7d/WeChatFerry/spy/message_sender.cpp#L46-L58)无需输入框，但 [RPC status=0](https://github.com/lich0821/WeChatFerry/blob/0f5c60a034fcac234cabd000b49c9200defa7f7d/WeChatFerry/spy/message_sender.cpp#L251-L262)仅在调用返回后赋值，没有返回该次发送的源 ID 或对端回执。这里不以 mock 或接口成功替代实机发送结果。

wxhelper [版本列表](https://github.com/ttttupup/wxhelper/blob/fa90a0ea87c9b4ca9c63a1e8385293159167f367/README.md#L20-L23)仍为旧 3.x；[SendTextMsg](https://github.com/ttttupup/wxhelper/blob/fa90a0ea87c9b4ca9c63a1e8385293159167f367/src/manager.cc#L222-L244)忽略内部返回后固定 success=1；[同步消息处理](https://github.com/ttttupup/wxhelper/blob/fa90a0ea87c9b4ca9c63a1e8385293159167f367/src/hooks.cc#L120-L154)虽保留 from/to/msgId/createTime，却不能证明后续投递、重启或历史同步行为。版本已不满足，未继续投入本机安装试验。

## 4. easyChat：4.1.15 字样没有解决最小化发送

本轮只追踪新版本发送链：[open_wechat](https://github.com/LTEnjoy/easyChat/blob/70f6f4122cbe18bc10ebe84527031627555a7824/versions/wechat_4_1_15_8.py#L78-L98)调用全局热键并检查微信成为焦点；[send_msg](https://github.com/LTEnjoy/easyChat/blob/70f6f4122cbe18bc10ebe84527031627555a7824/versions/wechat_4_1_15_8.py#L175-L206)按名称搜索、粘贴、Enter 后返回 True。它不满足窗口保持任务栏最小化，故不因版本较近而进入实现，不重复做 UIA 接收全面评估。

## 下一项最值得做的验证

**优先补 .50 的发送兼容性证据，暂不申请数据库密钥或试注入旧版 Hook。** 数据库入站仍是研究候选，但即使修好游标，也不能解决目前的最小化发送阻塞。

下一项应是一个有界的 **4.1.15.50 离线发送入口兼容性对照**，先形成以下可审阅材料：

| 必须交付的证据 | 通过条件 | 当前状态 |
| --- | --- | --- |
| 精确客户端构建 | Windows x64 的文件版本、模块哈希与来源对应 | 后续343/346已固定磁盘EXE/DLL的.50版本及哈希；不认证已加载进程内存 |
| 发送调用链 | 目标 wxid、对象布局、函数定位依据、线程调度均对应该构建 | 只有 .10.27 / .11.52 的固定偏移，不通过 |
| 最小化调度 | 无恢复窗口/焦点输入；明确安全点唤醒机制 | .11.52 有安全点依赖，最小化空闲实测缺失 |
| 请求身份与结果 | 账号代次 + 目标 + 请求关联；提交/失败/未知分开，未知停止 | 所查 success/布尔值不足，不能映射成已送达 |
| 配套接收 | 同来源的自身/目标/源ID语义、积压隔离、容量和断线处理 | 当前无合格完整来源 |

先要求公开 .50 源码、符号/定位依据或可核对的适配材料；不要把旧版固定 RVA 的数值落在新 DLL 范围内当作匹配。后续343–346已经执行本机安装文件的有界只读磁盘结构对照，没有加载 DLL、读进程内存、取密钥或写客户端；仍无函数语义/ABI证据，下一项是离线反汇编与调用关系分析，不能把静态定位当运行兼容证明。

只有精确构建与调用契约先成立，才值得提交最小范围实机方案供用户决定：隔离收发组件、单测试好友、模型/长期记忆断开、先只读接收，随后另行批准一次固定文本发送；全程记录真正最小化，超时/身份变化停止。安装/账号连接/注入与真实发送均没有因本文而获批，实际自动回复仍须最终确认。现有 Engine、模型、记忆、队列与去重代码保留待复用。

## 证据、许可与运行边界

[339](evidence/339-non-uia-expansion-manifest.json)记录固定 SHA、下载地址、46 份文本哈希/大小及未截断树元数据；缓存仅在忽略的 data/non-uia-expansion-20261005，第三方文本未提交。WeChatFerry 与 wxhelper 的固定 LICENSE 为 MIT；aixed 的树只找到 MinHook 的许可文件，navysoto/easyChat 未见项目许可文件。后者不等于禁止一切使用，但本轮没有建立可直接复制再分发的许可依据；公开可读不自动代表所有后续服务免费。

[340](evidence/340-hook-static-traces.json)保存静态反例与发送结果语义，[341](evidence/341-non-uia-expansion-validation.json)记录本地哈希/引用/文档检查，[342](evidence/342-non-uia-expansion-checkpoint.json)保存原监听只读状态。没有产品代码变化、版本升级或新适配器；没有产品回归/原生夹具/安装测试的新结果，既有 369 项通过保持其原范围。

原监听仍保存 stopped/native_reader_timeout，24569 成功快照、24505 最小化、unknown 1、防待机请求不活动；最小化字段只是最后观察。未重启、恢复窗口、改电源或补处理旧消息；没有个人配置/.env/密钥读取、真实聊天进入模型/长期记忆或实际发送。
