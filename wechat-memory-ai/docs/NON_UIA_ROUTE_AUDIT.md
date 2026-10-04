# 真正最小化：非 UIA 来源静态评估

2026-10-04 至 05 日（北京时间）。用户已选择“保留真正最小化，扩大非 UIA 方案的静态评估”。本报告保留普通个人微信既有好友会话、免费接入的目标；仅查公开资料和固定源码，不表示允许账号接入、安装、提取本机密钥、注入、改写客户端或发送。产品仍 v0.1.22。本轮未操作原 v0.1.21 监听，但最终检查发现它已超时停止，见末节。

**结论：非 UIA 路线能提供更好的结构化字段，但本轮没有找到已验证满足“本机 4.1.15.50、既有好友会话、免费、全程真正最小化收发”的可直接接入方案。** 这只限于下列来源，不是所有方案都不可能。官方 iLink 值得保留为独立机器人产品候选；数据库读取值得继续研究入站；网页协议有账号资格前提；所查 Hook 缺本机版本证据。

## 比较结果

“窗口独立”是所查代码路径的静态判断，均未经本机运行验证。最小化不等于系统睡眠时仍能工作。

| 路线 | 会话与身份范围 | 接收 / 发送是否依赖桌面微信界面 | 当前主要缺口 | 本项目决定 |
| --- | --- | --- | --- | --- |
| Tencent 官方 iLink Bot | Bot 账号、iLink 用户、Bot 直接会话；未见接管个人号既有好友聊天的接口证据 | HTTP 长轮询 / HTTP 发送，所查路径独立于窗口 | 产品会话范围不同；字段必填、游标恢复、发送结果须另验 | 保留为另一个产品方向，不能替换现有好友自动回复 |
| wechatauto-replica 数据库路线 | 本机普通聊天库、会话 username、发送者映射 | DB/WAL 读取独立于窗口；已查发送仍激活窗口/UIA/输入 | 4.1.15.13 声明不证明 .50；方向假设、消息 ID 丢失、序号边界和密钥获取 | 只作为入站研究候选，不能称全程最小化收发方案 |
| Wechaty Web provider | 登录网页微信后取得的好友/群与会话内 ID | 独立 Chromium，可 headless；发送走网页 bridge | 账号是否能登录未知，联系人 ID 跨登录变化，固定源码较旧 | 作为有条件候选；本轮未扫码，不认定可用 |
| Wechaty Puppet Service | 取决于具体 provider，不由统一 SDK 保证 | gRPC 服务；底层可能是网页、Pad 或 Windows | 长期免费资格、账号支持、底层实现与恢复语义均需逐 provider 证明 | “有 SDK / 有 token”不足以准入，不默认采购 |
| PC Hook：4.1.10.27 源码与 wxhook | 普通客户端内的接收/发送路径 | 所查 native 发送不靠输入框；真正最小化仍待实测 | 精确版本不匹配；回调/历史语义及结果确认未完成 | 不安装、不降级、不注入；不把 4.x 宣传当 .50 兼容 |

## 1. 官方 iLink：结构化 Bot 通道，不能偷换会话目标

固定 [Tencent/openclaw-weixin@24de5c9e](https://github.com/Tencent/openclaw-weixin/tree/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c)。登录结果区分 `ilink_bot_id` 与扫码用户 `ilink_user_id`；请求使用 Bot token，接口是 `ilink/bot/*`。源码能力声明只有 `chatTypes: ["direct"]`。因此本轮能确认的是 Bot 通道；未找到读取个人号任意既有好友/群聊或以该个人号回复的实现。类型里出现 `group_id` 也不能扩张支持范围。[登录协议](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/docs/protocol_zh_CN.md#L130-L160)、[能力声明](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/channel.ts#L229-L233)。

有利证据是明确的 `message_type`、`from_user_id`、`to_user_id`、`message_id`、创建时间、上下文 token 和分页游标。`message_id` 在 TS 类型中为字符串，API 解析保留 uint64 精度；同提交中文协议表仍写 number，集成时不能照表用浮点数。字段均可选，官方文档自己限定为客户端行为，不能当完整服务端契约。[类型](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/api/types.ts#L191-L243)、[无损解析](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/api/api.ts#L518-L578)、[文档范围](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/docs/protocol_zh_CN.md#L3-L19)。

不能直接复用的恢复/身份行为：

- monitor 先保存响应游标，再逐条调用处理器。若两步间退出，本地游标已前进而消息尚未处理；上游是否重发没有本轮证据，不能承诺不漏消息。[处理顺序](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/monitor/monitor.ts#L152-L182)。
- 入站上下文的 `MessageSid` 是本地生成，不能替代源 `message_id` 做持久去重；来源 ID 的提取函数另在同文件。未来桥接必须保留来源 ID 和账号作用域。[上下文](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/messaging/inbound.ts#L202-L209)、[本地 SID](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/messaging/inbound.ts#L250-L266)。
- 发送指定目标 iLink ID、Bot 类型、完成状态和上下文 token，确实走 HTTP；返回同时区分 client ID 与可选 server ID。缺少 context token 时客户端仅警告后继续请求，不能据此证明服务器接受；`sendMessage` 对缺失 `ret` 的对象也不抛业务错误，本项目不能把这种响应当确认送达。[请求及返回](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/messaging/send.ts#L56-L135)、[响应检查](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/src/api/api.ts#L580-L595)。

仓库为 MIT；这是代码许可证据，不是免费服务、额度或账号资格承诺。官方插件需要 Node/OpenClaw，并默认有本地引用缓存，因此即使未来改做 Bot 产品，也要先审阅运行依赖及数据保存策略，不能在当前“真实聊天不进记忆/模型”的阶段直接启动整个 Gateway。[README](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/README.zh_CN.md)、[LICENSE](https://github.com/Tencent/openclaw-weixin/blob/24de5c9eb0dd5e595d7e2d090ed8a3f82870d42c/LICENSE)。

## 2. 数据库：有价值的接收来源，现成发送仍会恢复窗口

固定 [wechatauto-replica@91dc0e1a](https://github.com/fanyuantaier/wechatauto-replica/tree/91dc0e1a601013b759b261061d8f7642f736af90)，更新了此前核查的旧 SHA。README 声明验证到 4.1.15.13，不能证明本机 4.1.15.50。读取 encrypted DB/WAL 后有会话 username、发送者映射、服务器 ID、创建时间和排序序号，结构比 UIA 文本丰富。[版本说明](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/README.zh-CN.md#L19-L31)、[原始查询](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L1731-L1765)。

具体接入缺口：

- 原始查询读了 `server_id`，但给监听用的 `_msg_row_to_dict` 没有把它传出，也不带分片身份；`local_id` 不能跨分片当唯一消息 ID。[输出字段](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L1986-L2040)。
- 监听查询用 `sort_seq > since_seq`，默认最多 200 条，水位只有一个序号。静态反例：201 条消息同为序号 S，第一页返回 200 条后水位到 S，剩余一条不再满足 `> S`；延迟落库的同序号消息也类似。源码自身承认序号有重复，这不是本机故障复现。注册监听时取当前最大序号作基线，也不能证明后续更大序号绝非历史同步。[排序注释](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L1731-L1750)、[基线](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L2811-L2826)、[轮询及水位](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L2901-L2959)。
- `wx.py` 用 `sender_id == 2` 或与 self ID 比较判自身，否则标 friend；发送者映射缺失时还能回退正文前缀/数字。这个包装器不保留可靠的 unknown 分支。需独立绑定自身账号、目标 username 并验证原始映射，不能直接接受 `attr='friend'`。[方向包装](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/wx.py#L240-L289)、[映射来源](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L2375-L2394)。
- 回调失败重试耗尽后仍推进水位，是有记录的丢弃策略，不能包装成可靠确认。[工作线程](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L2941-L2959)。

发送路线需要 `ensure_window` 激活界面；相关前台函数对最小化窗口调用恢复，之后粘贴及 Enter，另一分支调用 `ensure_visible`。因此“后台 DB 接收”不能推导“后台发送”。[发送](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/uia_driver.py#L1568-L1582)、[窗口激活](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/uia_driver.py#L883-L903)、[前台要求](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/guia.py#L997-L1022)。

运行还涉及进程内密钥读取、解密副本；UIA 驱动另有写进程内存路径，不能因为 DB 读取部分只读就把整个包称为无修改。[读进程路径](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/db.py#L1075-L1098)、[驱动内存写入](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/wechatauto/uia_driver.py#L671-L684)。本轮均未执行。仓库 Apache-2.0；未分发其代码。[LICENSE](https://github.com/fanyuantaier/wechatauto-replica/blob/91dc0e1a601013b759b261061d8f7642f736af90/LICENSE)。

## 3. 网页协议与结构化服务：条件分别核验

固定 [wechaty-puppet-wechat@09fedb14](https://github.com/wechaty/wechaty-puppet-wechat/tree/09fedb147bebee1e28ac03c50debb7267af4b3d9)，HEAD 提交日期为 2022-07-14。解析器取 `MsgId`、`MMActualSender`、`ToUserName`、`MMDisplayTime`；时间来自 Web 层显示字段，不能直接认证服务器新到达。发送使用 conversation ID 调用 browser bridge，浏览器可 headless，因此架构上不必恢复 PC 微信窗口。[解析](https://github.com/wechaty/wechaty-puppet-wechat/blob/09fedb147bebee1e28ac03c50debb7267af4b3d9/src/pure-function-helpers/message-raw-payload-parser.ts#L18-L79)、[发送](https://github.com/wechaty/wechaty-puppet-wechat/blob/09fedb147bebee1e28ac03c50debb7267af4b3d9/src/puppet-wechat.ts#L470-L482)、[浏览器](https://github.com/wechaty/wechaty-puppet-wechat/blob/09fedb147bebee1e28ac03c50debb7267af4b3d9/src/bridge.ts#L128-L151)。

维护方文档仍列出部分账号不能登录 Web、联系人/群 ID 跨登录变化、UOS 登录补丁不能继续使用等限制。固定仓库的旧 README 第21行却仍称 UOS 已解决登录问题，两处资料不一致。它们不是对用户账号的检测结果，也不能保证 2026 年服务可用。未来若获得登录授权，首个实验应只验证账号资格与会话身份变化，不能扫码后直接连接模型或处理积压消息。[provider 文档](https://wechaty.js.org/docs/puppet-providers/wechat/)、[旧README](https://github.com/wechaty/wechaty-puppet-wechat/blob/09fedb147bebee1e28ac03c50debb7267af4b3d9/README.md#L17-L23)。

Puppet Service 则是 SDK 到具体服务的授权通道，不能把接口结构当底层实现证据。维护方文档将 token 分为短期试用、贡献者长期免费和付费；不能把短期试用算作用户要求的长期免费。未申请 token、联系服务商或比较实时售价。[token 说明](https://wechaty.js.org/docs/puppet-services/tokens)、[服务机制](https://wechaty.js.org/docs/specs/service/)。

## 4. Hook：真后台的架构潜力，缺精确版本及交付证据

固定 [WechatHook4.1.10.27@713ec7d6](https://github.com/mosheng20205/WechatHook4.1.10.27/tree/713ec7d6f01d858e067a623c9bf2cda64d0d3e19)。维护方声明接收可取得 sender/receiver，且明确偏移仅适用于 4.1.10.27。本轮核查的文本发送函数直接构造对象并调用 Weixin.dll 内部函数，HTTP 返回 `queued`，不代表服务端或对端送达。这说明存在不经 UIA 输入框的路线，不证明能运行于 .50 或已完成真正最小化实测。[版本与接收声明](https://github.com/mosheng20205/WechatHook4.1.10.27/blob/713ec7d6f01d858e067a623c9bf2cda64d0d3e19/README.md#L1-L15)、[HTTP 结果](https://github.com/mosheng20205/WechatHook4.1.10.27/blob/713ec7d6f01d858e067a623c9bf2cda64d0d3e19/src/SendTextMsg.cpp#L30-L54)、[native 调用](https://github.com/mosheng20205/WechatHook4.1.10.27/blob/713ec7d6f01d858e067a623c9bf2cda64d0d3e19/src/wx_send.cpp#L501-L532)。

没有借此认证回调中的历史边界、消息 ID、重放或重连完整性，也没有完整审计 native 内存安全。树中仅见 vendored MinHook 许可证，未见项目根许可；公开源码不自动等于可直接再分发。版本与许可都未满足，暂不进入运行验证。

另固定 [miloira/wxhook@d6d1cecd](https://github.com/miloira/wxhook/tree/d6d1cecd7c13f347b776a49442ecadadae55d5ec)：页面宣传的新 3.x/4.x 框架要求另行获取，而公开 `core.py` 的版本仍为 3.9.5.81，并使用注入启动。不能将页面标题的新版本范围归到此公开源码或认定新版本免费。[README 区分](https://github.com/miloira/wxhook/blob/d6d1cecd7c13f347b776a49442ecadadae55d5ec/README.md#L111-L118)、[公开实现](https://github.com/miloira/wxhook/blob/d6d1cecd7c13f347b776a49442ecadadae55d5ec/wxhook/core.py#L45-L75)。

## 后续可审阅的验证顺序

保留既有好友会话目标时，先把数据库候选限定为只读入站研究：补齐服务器 ID/分片身份、显式 unknown、同序号游标和历史同步边界，再考虑是否值得申请最小范围运行验证。它仍需要独立的非 UI 发送来源；目前所查 Hook 版本不匹配，因此不能承诺用“DB + Hook”直接拼出可用方案。

网页路线只有确认账号可登录后才值得集成；官方 iLink 只有在用户另选 Bot 会话产品时才成为优先候选。无需为本次静态评估重复征求开发权限；任何登录、密钥读取或客户端修改都不是本轮实施步骤。真实自动回复继续按既有约定，在具体功能和方案完成、可审阅后取得最终确认。

所有候选至少要提供：账号和目标绑定、方向及未知拒绝、来源消息身份、启动/重连积压边界、失败可恢复的处理游标、发送结果不明后的停止策略。`ret=0`、本地 queued、本地新 ID 或收到回调，都不能单独代表对端送达或实时新消息。

## 证据与边界

[331清单](evidence/331-non-uia-source-manifest.json)固定 5 个仓库的 47 份公开文本、SHA256、字节数和源码位置。正文只对引用路径作具体结论，不声称完整安全审计。原文件在忽略的 `data/non-uia-audit-20261004`，未提交第三方源码、安装包或二进制。两处企业微信文档及公众号文档访问失败，未拿搜索摘要补作已核实结论；它们不参与本轮准入。

本轮没有产品代码或版本变化，没有新适配器、账号登录、第三方执行、真实聊天读取实验、模型、聊天记忆或发送；只查看原监听脱敏状态。未重跑产品回归、原生夹具或安装测试，既有 321/322 的 369 项结果保持其原范围。文中的边界例子是静态推演，不冒称新的运行测试。

[332静态校验](evidence/332-non-uia-static-validation.json)验证47份文件哈希/大小、固定源码引用及本地链接。[334独立复审](evidence/334-non-uia-review.json)未发现实质错误；审查未联网复验3个Wechaty网页，网页条款来自主执行者的公开检索，不冒称双重验证。

[333最终状态](evidence/333-non-uia-checkpoint.json)：原监听已因 `native_reader_timeout` 停止，累计24569次成功快照、24505次最小化、unknown1；第24570次调用为首次超时。外层745786ms，原生completed745479ms，耗时主要在request_read与client_lookup之间。现有证据不能归因于待机或某个微信操作。防待机requested仍true、request_active已false；`window_minimized=true`是停止状态保存的最后观察，不能作为停止后的实时窗口认证。本轮未重启、恢复窗口或补处理积压，后续先调查超时并按既有防待机偏好处理恢复。
