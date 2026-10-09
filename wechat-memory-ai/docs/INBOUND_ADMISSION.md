# 最小化真实入站：能力证据与准入条件

## 最新：快照、ETW与Windows通知尚不能补齐来源（507–509）

2026-10-09。[替代来源报告](OS_RECEIVE_SURFACE_AUDIT.md)核查三个具体OS接口。通知ID/应用身份/图标ID不能自动映射为微信消息、账号或好友；入口参数快照没有事件保留契约；通用ETW无已识别消息提供者。固定DLL气泡通知路径只说明存在相关代码，未验证聊天执行或通知监听器交付。

因此没有新增真实桥接或verified开关，当前准入仍关闭。此结论仅覆盖本轮候选与固定检查，不证明所有通知/ETW/只读缓冲方案不可能。[507](evidence/507-os-receive-contracts.json)、[508](evidence/508-os-receive-disk-audit.json)、[509](evidence/509-os-receive-checkpoint.json)。


## 最新：scene 消费者与集合写入核查收敛（468–471）

2026-10-09（北京时间）。[续查记录](INBOUND_EVENT_ORIGIN_4_1_15_50.md)已补scene三种不同数值规则：[468](evidence/468-inbound-scene-consumers.json)确认它们分别影响特定支路，不能合并为is_live。17c7fb0尾部掩码命中返回false；新建解析对象时缺scene和显式0可落到相同值，不能从0认证实时消息。

[469](evidence/469-inbound-key-set-writers.json)找到23be9a0集合的三处插入调用。键为条件选用的消息+2c8字符串，或选定字符串与两个DWORD拼接，并非AddMsg字段12。命中消费会删除节点，后续缺项不代表第一次收到；写入点、内部投影及返回值也不认证数据库提交或历史水位。

本轮结束这两项作为单独自动回复准入判据的定点核查。后续回到具体采集器的初始同步/重连/逐条交付语义；没有来源证据前保留unknown，不再猜scene、换集合或增加verified开关。没有可运行的真实最小化适配器；接收核查不代表发送解决。

[470](evidence/470-inbound-consumers-validation.json)为同一执行者的新鲜静态复核与数值推导，未跑产品或微信测试。[471](evidence/471-inbound-consumers-checkpoint.json)保存产品0.1.22、自动回复关闭、监听保存停止状态；无Jev/其他判断模型、进程/密钥/聊天数据库/窗口/发送操作。最低已知额度剩余58%，既有id40不变，后续证据从472起。

## 最新：逐条消息来源与默认文字分支（464–467）

2026-10-09（北京时间）。[具体核查](INBOUND_EVENT_ORIGIN_4_1_15_50.md)沿同一哈希的.50 DLL磁盘只读推进。[464](evidence/464-inbound-msgsource-provenance.json)绑定AddMsg字段10→内部+1c0→msgsource解析器；scene的存储位置已知，数值域和新旧含义仍未知。share_msg的时间/ID属于嵌套引用，不能替换当前消息身份。解析失败或空串后外层仍可设置+2c0，故“已处理”不证明解析成功或实时来信。

[465](evidence/465-inbound-deferred-text-gate.json)接通434的延迟闭包：先查handler虚槽+48，true才传模式给+40。默认TextMessageHandler的+48固定false，该分支不能作为文字实时/历史过滤器；实际receiver和注册覆盖仍待认证。闭包前后调用的23be9a0是命中后删除集合元素的操作，非无副作用查询，其写入来源和键含义未知。

[466](evidence/466-inbound-origin-validation.json)记录同一执行者的新鲜磁盘字节/指令/表槽与历史文件哈希复核，非独立审查或实机验收，本轮没有新增或重跑产品测试。[467](evidence/467-inbound-origin-checkpoint.json)保存产品0.1.22、自动回复关闭、监听保存停止状态；无进程/数据库/密钥/窗口/发送或外部判断模型调用。

下一步仅限msgsource.scene的具体消费者和值域，或23be9a0集合的具体写入来源；未认证前保持unknown，不扩散通用NewSync偏移、不添加verified开关。接收核查不代表最小化发送已解决。最低已知额度剩余61%，既有id40监测不变；后续证据从468起。

## 最新：固定数据库候选定点核查结束（461–463）

2026-10-09（北京时间）。[方案结论](DB_COLLECTOR_FEASIBILITY.md)现将wechatauto-replica固定fbfb026排除出无人值守真实入站实施候选，保留离线结构参考。[461](evidence/461-db-route-closure-audit.json)核对完整77份Python及2份文档：消息source仅透传，packed_info用于媒体标识/文件名；未找到实时/历史分类器。8处SQLite连接分别为原副本读取/校验、导出、镜像或测试库，没有另一条已提交快照入口。该结论不外推为所有数据库路线不可能。

[462](evidence/462-db-raw-metadata-validation.json)新增3项自写内存SQLite反例通过：按local_id补取raw元数据可能取到其他分片；类型过滤或固定排序不认证原消息。未重跑上轮18项/243组，也未重跑456的101项。[463](evidence/463-db-route-closure-checkpoint.json)保持产品0.1.22、自动回复关闭及监听保存停止状态；没有微信/进程/密钥/窗口/发送或外部判断模型调用。

此DB候选的定点核查结束，不再靠修补其Listener推进准入。后续只针对已定位.50逐条事件的历史/实时来源补证据，保留身份/退出缺口；不重复泛化NewSync偏移。额度最低已知剩余64%，既有id40监测不变；后续证据从464起。

## 最新：数据库采集器方案与离线反例（458–460）

2026-10-09（北京时间）。[具体方案](DB_COLLECTOR_FEASIBILITY.md)已完成；[458](evidence/458-db-collector-source-audit.json)复核固定候选fbfb026的7份文本与22处锚点。候选仍仅声明实测4.1.15.13，不证明本机.50。除了交接中的分页/水位/队列问题，本轮确认接收包装仍固定sender_id=2为自己，WAL合并函数未消费提交标记/帧累计校验；不能直接安装接入。

[459](evidence/459-db-collector-counterexamples.json)为自写18项离线案例通过，含243组固定快照分页比较；不执行上游或产品，不访问真实聊天。复合游标仅修正固定快照内分页；晚到低序号和历史仍不能识别。合成未提交尾页可通过quick_check，不能用结构可读代替事务来源。没有可准入来源，因此未增加产品桥接或verified开关。

下一步只围绕一致快照获取和实时/历史可区分来源收敛，缺来源就保持观察用途；不继续堆通用NewSync偏移，也不以读库代表最小化发送。[460](evidence/460-db-collector-checkpoint.json)保存本轮边界：产品0.1.22、自动回复关闭、监听保存状态仍停止；未操作窗口/进程/真实数据库/密钥、未安装或发送，无Jev/其他判断模型调用。最低已知额度剩余67%，既有id40监测不重复创建。后续证据从461起。

## 2026-10-09：从现有代码能否直接实现接入

**不能直接接通。当前有读取界面变化的工具，没有满足本目标的真实收发适配器。** 本次逐项检查源码，不重读微信窗口。源码哈希、24处锚点及7类组件清单见[455](evidence/455-minimized-source-feasibility.json)；本轮101项选定离线回归见[456](evidence/456-minimized-source-validation.json)。下方10月4日实机记录是历史观察，不代表当前仍在监听。

| 现有来源/组件 | 实际提供什么 | 为什么不能直接用于最小化自动回复 |
| --- | --- | --- |
| [background读取](../src/wechat_memory/live_reader.cs) | 同一窗口/列表绑定、IsIconic值、行token/类型/Name文字；两次读取一致性复核 | 协议没有账号、sender、收发方向、服务器ID或同步阶段。两次相同也不是原子消息事件 |
| [BackgroundOccurrenceSession](../src/wechat_memory/live_read.py) | 首屏跳过、行变化连续性、本地UUID/序号；方向固定unknown | 首屏之后追加仍可能是自身消息或历史同步；本地epoch是观察会话标识，不是微信账号/重连代次 |
| selection读取 | 多选标签与昵称前缀生成incoming_candidate | 前缀不能认证发送者，不能替换background后宣称方向已解决；不操作窗口进入多选 |
| [ReadOnlyWeChatSource](../src/wechat_memory/live_source.py) | 有界、同线程的visual_text读取；本地候选对象有效期；随机标记边界 | poll固定要求视觉协议，原生拒绝最小化；marker_boundary_observed不排除后续历史同步，observed_at仅本地观察时间 |
| [能力报告](../src/wechat_memory/inbound_capabilities.py) | 属性存在性、计数、滚动属性 | 输出始终admission=rejected；即使所有属性存在也不补身份语义 |
| [monitor](../src/wechat_memory/monitor.py) / [CallbackInbox](../src/wechat_memory/callback_inbox.py) | 前者计数后丢弃候选，后者搬运已构造Event、清理本地队列 | 没有微信内部订阅。inbox代次、pending=0或source.close都不认证客户端回调已退出 |
| [Adapter](../src/wechat_memory/adapters.py) / [Engine](../src/wechat_memory/engine.py) | MockAdapter和模拟outbox；Config/Engine只接收mock | 仍缺real poll、真实目标绑定send与送达判据；把真实输入包装成默认is_self=false的Event属于伪造来源 |

一个合成background快照在首屏后追加一行，代码只能给出unknown；其字段不能区分“对方新来信”“自身消息”“较晚显示的历史”。这是协议信息不足的示例，不是三次微信实机复现。手工补入account_id、sender_id、direction、server_message_id、sync_phase或identity_epoch均被严格协议拒绝；打开一个布尔开关不会产生缺失事实。

### 将452的条件对应到现有实现

| 452中的客户端事件 | 当前可取得的相似信息 | 结论 |
| --- | --- | --- |
| cancel_requested | Python监听收到stop指令 | 只停止自己的观察，不是微信请求取消 |
| network_stop_executed | 无 | 没有客户端enable位/StopTask的采集器 |
| map_entry_removed | 本地inbox pending计数 | 不是微信网络任务映射 |
| timeout_handle_removed | NativeReader子进程超时与阶段耗时 | 不是微信NewSync的计时句柄 |
| callback_exited | Python来源关闭、读取子进程结束、本地代次失效 | 不证明微信完成/停止/超时回调退出 |
| observation_ready | 窗口绑定、minimized、baseline_ready | 只覆盖界面观察条件，缺消息身份语义与真实来源 |

这张表用于阻止把不同层级的信息误当成同一件事。**452和O1–O7的内部对象字段只约束采用相关内部调用/回调的方案；独立来源不必复制微信全部内部状态。** 所有方案共同需要：稳定账号与目标关联、可信方向、可解释的消息ID及历史/重连策略、采集器有界交付和停止机制。发送能力另行验证。

### 本轮决定与明确的实现顺序

1. 结束“多等几条unknown或继续核普通NewSync包装层即可接入”的路线。现有静态研究可作候选实现参考，不能代表已经完成采集器。
2. 先准备一个具体采集器方案：写清入口/API、精确版本和许可、能获得的原始字段、如何关联账号与单好友、如何区分实时/历史、如何解绑与退出。未确认的项保持未确认，不用更多必需字段掩盖没有来源的事实。
3. 方法具备依据后，先完成隔离实现与离线验证；若需要额外运行权限，给出具体范围和退出办法后再请求，当前不执行进程/数据库访问、安装或注入。
4. 接收实机验收通过后，再验证目标绑定发送、模型与记忆，最后按既定确认启用自动回复。目前无法给出可靠启用时间。

精确版本公开检索补查了3个GitHub限定查询，搜索工具没有返回结果；仅说明本次索引未找到匹配，不能推断不存在兼容项目，也没有复核任何上游HEAD。没有据此安装组件或改换Bot/Web方案。

2026-10-04，v0.1.22。**当前普通最小化 UIA 来源仍拒绝进入回复核心。** 本版新增的是可复查的能力检查和拒绝报告，没有实现可接受真实消息的桥接或发送器。

后续已完成两UIA候选固定源码和规则反例核查，未找到可直接采用的来源；证据及范围见[SOURCE_ROUTE_AUDIT](SOURCE_ROUTE_AUDIT.md)。用户已选择保留真正最小化、扩大非UIA静态评估；[NON_UIA_ROUTE_AUDIT](NON_UIA_ROUTE_AUDIT.md)进一步核查5仓库47份文本，仍无可直接准入来源。结构化字段与回调不能代替账号/方向/历史验证。产品源码和现有监听未改。

## 实机发现

[316](evidence/316-live-inbound-capabilities.json)的三次独立诊断均确认最小化，结果一致：8 行中有 5 个文本项，5 个文本项都有 AutomationId，而所有行的非空 AutomationId 总共只有 1 个；文本项没有 HelpText、ItemStatus、ItemType、LabeledBy、TextPattern 或子控件。消息列表及向上直到已绑定窗口根的 7 层祖先，共 8 个节点，都没有 ScrollPattern。

因此，这次检查的字段没有提供可验证的方向、独立消息身份或滚动边界。窗口 AutomationId 与进程/窗口/列表绑定仍只限定窗口实例，未认证联系人身份。这个结论仅覆盖当前客户端、账号、窗口和所检查属性，不证明所有 Windows 接口或未来版本都没有其他能力。

[320最终复查](evidence/320-live-inbound-final.json)在祖先范围检查收紧后，再次三次全部最小化且取得相同结果；单次343/329/343ms。原监听到1376次、1312次最小化，unknown仍1、0超时、防待机活动。新代码没有替换原运行进程。

三次诊断耗时 344/328/328ms，是一次元数据读取的耗时，不是从发送到收信的延迟。原监听在探测前后从 1123→1124 次快照、1059→1060 次最小化，unknown 累计仍为 1，0 超时，防待机继续活动。没有重启、恢复窗口或发送消息。此前 308/309 的受控新增文本证据继续有效，无需重发同一输入。

## 实现与数据边界

`NativeReader.read_inbound_capabilities()`必须已有绑定；原生入口也拒绝空绑定。在读取消息项元数据之前，沿用进程启动时间、窗口、根和消息列表绑定检查。祖先路径必须到达绑定根，才读取其滚动属性。只读取 ScrollPattern 的当前属性，不调用滚动、输入或任何发送 API。

同一窗口连续采两组元数据，比较行 token、类型、属性存在性、私有辅助属性值、祖先路径 token 及滚动值，再复核绑定与最小化状态。变化返回 `inbound_capabilities_changed`；没有自动重取、重绑或提升候选。该双读不读取消息正文，也不提供原子消息快照。

原生协议含私有绑定和行 token，只在进程间内存传递；必须经过 `inbound_capability_report()`严格校验后才能输出。公开报告只有固定字段、计数、布尔值、层级和滚动百分比，额外字段、非法类型、重复 token、计数矛盾、非法百分比一律拒绝。辅助属性值仅在原生内存比较，不输出、散列存档或传入模型。

316 的诊断启动先调用现有 background 读取取得唯一授权测试窗口的绑定。这一步会在内存读基线正文，随后丢弃，没有输出/保存或视为入站；三次能力诊断本身不读取 Name、TextPattern 内容或像素。两者在证据中分别记录，不能把整个启动步骤宣称为从未读取正文。

能力报告的 `admission=rejected` 是诊断结论，不是消息准入令牌。所有元数据存在、滚动值为 100，也仍返回四项未验证原因。报告不能进入任一消息会话；Config/Engine/mock 限制保持不变，监听仍只计 unknown，不调用本报告或回复核心。

## 真正可接受入站前的证据要求

| 条件 | 必须能核验的来源事实 | 拒绝路径 |
| --- | --- | --- |
| 收发方向 | 源明确给出本机账号/对方角色，并通过新的自身与对方事件对照；不能以“不像自身”推为来信 | unknown、自身、矛盾角色拒绝；当前 `direction_unverified` |
| 目标身份 | 来信事件、授权对象和发送目标绑定到同一稳定会话身份，切换/重开后有独立复核 | 昵称相同不合并；当前 `target_identity_unverified`；绑定变化终止 |
| 新事件与历史 | 源能区分实时到达、历史同步、重放及停机补入；首基线和历史均不交付 | 无法判定时拒绝；当前 `history_boundary_unverified`；连续性丢失终止 |
| 消息身份 | 源提供有证据支持的事件标识和去重范围；本地 observation_id/RuntimeId/正文哈希不能替代 | 复用、冲突、旧组合重现拒绝；当前 `message_identity_unverified` |
| 有效期 | 已接受事件绑定在未关闭、未到期、未失效的来源；模型前和发送前独立复核 | 失效后不重绑旧事件，不能靠写当前时间“刷新” |

当前来源没有上述语义验证器，所以没有任何 `accepted` 分支。不能新增可由调用方填写的 `verified=true` 开关把它接到 Engine。后续隔离桥接须由具体来源产生并核验这些证据，且先证明拒绝事件对模型、Store、预算及 outbox 均为零调用。到时才能实现接收路径，不能为了测试绿色而给真实候选伪造 mock 身份。

## 可替代路线及选择

1. **相同 UIA 来源的第三方封装**：可以静态比较其事件来源，但封装本身不会创造上述缺失证据。2026-10-04 核对 [wxauto 安装文档](https://docs.wxauto.org/docs/install.html)，免费版仍只声明支持到 4.1.8.107；不是本机 4.1.15.50 的兼容或最小化验证。不安装不匹配包、不购买 Plus。此前 pyweixin 发行包与许可证据见 [FREE_ROUTE](FREE_ROUTE.md)，本次没有重做发行包审核或运行它。
2. **窗口可见时的视觉来源**：已有受监督方向候选和自身过滤证据，但需要非最小化，不能满足用户目标。保留研究结果，不恢复窗口来替代后台能力。
3. **提供结构化事件的独立来源**：方向、会话与消息标识可由此来源提供，再按上表逐项实证，是后续接入核心所需的能力类型。当前没有验证可直接替换本机来源的免费实现。[wechatferry Node 客户端指南](https://github.com/wechatferry/wechatferry/blob/main/docs/guide.md)仍要求 3.9.12.17，不证明兼容本机 4.1；不降级微信、不引入进程注入/密钥提取或改写客户端内存。既定普通个人微信与正常 UI 路线的范围保持不变。

后续优先静态核验其他免费来源是否真的提供上表证据；只有发现适用且符合既有范围的来源，才做独立只读接入和受控验证。反复发送同样测试消息、等待更多 unknown 或放宽阈值，不能补出这些缺失字段。当前不能给出可靠后台自动回复已经可实现的结论。

## 后续发送接入边界

只有入站证据通过后，才建立独立会话映射与发送适配器；模型不得持有 UI、配置或发送权限。发送前需重新核对真实目标，失效、目标改变或结果不明确即停住，不自动重试。`ReadOnlyWeChatSource.is_current`仍不是发送许可。真实模型质量还需用虚构内容复验 206 的失败；实际微信自动回复继续等待方案和功能可审阅后的最终确认。

实现参考：祖先是否到达同一根使用 [AutomationElement 相等运算符](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.op_equality?view=netframework-4.8.1)。它只判断同一 UI 元素，不认证联系人。初次编译把比较误写为该类不存在的方法，314/315 保留失败；修正后才取得 316 实测。
