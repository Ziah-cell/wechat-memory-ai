# Windows 测试结果（当前源码 v0.1.22）

## 最新：共享调试对象接手有进展，最终39次夹具对照符合预期（486–489）

2026-10-09。沿用475授权，增加第四种恢复办法：在附加前保留同一个调试对象，观察进程退出后恢复进程接手。初版15次中3次在“事件已交付、尚未处理”时单步异常退出；加入事件重报后27次对照符合预期。继续补查发现9次安装前/正常脱离后的清理状态错误，按实际调试关系和启用槽修正。[完整报告](BOUNDED_RECEIVE_DEBUG_OBJECT_TRANSFER.md)、[486失败与重报](evidence/486-bounded-receive-debug-object-transfer.json)保留原结果。

[487最终验证](evidence/487-bounded-receive-transfer-lifecycle.json)：13类场景各3次，共39次符合预期，36次继续运行、3次保留UD2致命退出；包括真正观察进程硬退出、事件处理前后、恢复进程单独退出、附加/安装中及正常200次预算结束。故意延迟200毫秒接手，目标自主调用或立即发起下一调用，不等待清理；该延迟不证明达到100毫秒停顿预算。原观察器与原失败测试保持。

[488核查](evidence/488-bounded-receive-transfer-validation.json)绑定9批97次运行及8份旧代码版本，保存302份旧证据、29份产品源码、24份历史脚本和上一轮7份源码。未重跑产品或原完整原生回归。[489检查点](evidence/489-bounded-receive-transfer-checkpoint.json)仍关闭微信准入：当前仅主线程实验，尚需同一最终实现的新/退出线程、有界读取、取消/目标退出和预算验证；双角色同时故障及Native API稳定性未证明。产品0.1.22、自动回复关闭、旧监听保存停止，无微信/窗口/密钥/聊天库/发送/Jev操作，无遗留测试进程。现有授权有效，直接推进上述集成，不重复询问。额度最低已知剩余44%，id40不变，后续从490起。

## 最新：三种恢复办法实测，前端故障隔离有进展（482–485）

2026-10-09。用户要求“继续，尝试多种办法”，本轮在自建子进程比较一次性硬件断点、独立调试进程及原生Windows调试API。[比较报告](BOUNDED_RECEIVE_METHOD_COMPARISON.md)与[482](evidence/482-bounded-receive-method-comparison.json)：选定30次对照15恢复、15未恢复。一次性断点首次命中后6次恢复，但命中前3次仍失败，且先遇到非标记消息会漏掉后续标记；原生API的9次强制退出对照同样单步异常。

[483](evidence/483-bounded-receive-broker-cleanup.json)定位连续调用取消时沿用旧停止点、重复请求GO的清理问题；第一次局部修正仍失败，最终实验子类在空闲前端退出3次、连续调用前端退出9次均恢复。但持有断点的调试进程自身退出3次仍全部失败，不能降低原门槛或把前端与调试所有者混为一谈。测试期间目标自主连续调用，不等待清理，不吞掉异常。初次批次因测试脚本未捕获TimeoutExpired中断，已有14条结果保留；后续改为记录失败，没有放宽超时。

[484](evidence/484-bounded-receive-method-validation.json)绑定各运行版本。原观察器/失败测试、29份产品源码、24份旧研究脚本及298份旧证据保持；未重跑产品或原完整原生回归。[485](evidence/485-bounded-receive-method-checkpoint.json)保持产品0.1.22、自动回复关闭、旧监听保存停止状态，尚无微信运行入口；本轮只操作自建程序，无微信/窗口/密钥/聊天库/发送/Jev。无遗留测试进程。授权有效，不重复问。后续必须解决真正持有断点者的硬退出生命周期，或比较不持续改变目标调试寄存器的具体来源；不再仅换标志、进程名称或重复相同失败。额度最低已知剩余47%，id40不变，后续从486起。

## 最新：强制退出断点残留已定位，当前观察方法不进入微信（479–481）

2026-10-09。沿用475授权，在自建夹具读取调试寄存器。[诊断结论](BOUNDED_RECEIVE_CRASH_DIAGNOSIS.md)：已返回调用后强制结束观察器的6次对照，DR0仍指向夹具函数、DR7=0x401、TF=0，下一次调用均单步异常退出；其中3次先等400毫秒仍失败。正常分离清零并恢复。另3次armed后立即结束留下暂停计数1和启用的断点，最终只由创建者清理测试夹具。[479](evidence/479-bounded-receive-crash-registers.json)保留14次诊断对照和首轮线程权限常量错误，不能算14项通过。

手工在下一次调用前禁用残留断点的3次对照恢复，但这依赖测试脚本控制调用次序，不能当作守护进程自动恢复。原观察器及失败测试未改；夹具仅增主线程ID输出。[480](evidence/480-bounded-receive-crash-validation.json)新跑原有3项：2通过、强制结束恢复1失败，命令退出1。29份产品源码、24份旧研究脚本和295份先前证据保持；未重跑完整原生/产品回归或离线投影。

当前直接DbgEng硬件断点方法结束普通清理补丁/增加等待方向的尝试，仍无可验证的异常退出恢复，不能进入微信。后续须先提出不依赖“清理抢在目标再次执行之前”的生命周期机制，否则重新评估具体采集来源；不循环扩展偏移、增加verified开关或把手工恢复并入验收。已有授权有效，不重复询问。[481](evidence/481-bounded-receive-crash-checkpoint.json)保持产品0.1.22、自动回复关闭、旧监听保存停止状态；本轮无微信/窗口/密钥/聊天库/真实发送/Jev操作，确有自建夹具调试、寄存器读写与清理。额度最低已知剩余50%，id40不变，后续从482起。

## 最新：已授权；原生夹具未通过退出门槛（475–478）

2026-10-09。用户“同意，继续”已批准上一轮有界观察方案，[475](evidence/475-bounded-receive-authorization.json)保存范围，**授权持续有效，不再重复询问**。本轮实现外部DbgEng观察器及自建原生夹具，实际进程操作仅针对本项目自己的子进程；当前CLI只有fixture模式，没有微信入口。[结果与继续边界](BOUNDED_RECEIVE_NATIVE_RESULTS.md)。

[476](evidence/476-bounded-receive-native-results.json)最终12项中11通过、1失败（11项原生夹具+1项固定SDK接口核查）。普通/新线程命中、取消、超时、布局错误、上限、目标退出及异常透传均通过；但强制结束观察器后，夹具再次调用受观察函数产生single-step异常并退出1。保留真实失败，不改expected-failure，不视为微信故障。按已批准的“任何一项失败都不连接微信”，未进入实机。

[477](evidence/477-bounded-receive-implementation-validation.json)记录修复过的COM槽位遗漏、初始中断配置、正常分离前消费单步事件、有限等待后的清理上下文及取消释放同步。29份产品源码、24份旧研究脚本、292份先前证据保持；未重跑产品回归。不能把系统调试库加载及夹具内存读取写成“没有进程操作”。

[478](evidence/478-bounded-receive-native-checkpoint.json)保持产品0.1.22、自动回复关闭、旧监听保存停止状态；没有微信进程/密钥/数据库/窗口/真实发送或Jev操作。最终未发现遗留夹具/观察器。最低已知额度剩余52%，id40保留，后续从479起。下一项只在自建夹具验证强制终止恢复，另有附加中途崩溃等未测边界；不请求测试消息、不跳过失败、不改软件断点/注入、不放开发送。

## 最新：有界接收观察方案待授权（472–474）

2026-10-09。[具体方案](BOUNDED_RECEIVE_PROBE_4_1_15_50.md)提出一次外部调试器观察：先自建原生夹具验证，再在固定.50消息转换入口，用本次随机标记检查最小化接收；最多120秒/200次入口命中/1次匹配即请求退出。调试附加会控制执行并暂停线程、读取限定消息内存，因此须用户批准该具体新增范围；现在未授权、未实现调试器、未连接微信。退出预算不是系统调用必然按时完成的保证。

[472](evidence/472-bounded-receive-proposal-basis.json)确认两处Hook候选HEAD均未变化，并复核1个函数/11条指令/3个字节窗口。[473](evidence/473-bounded-receive-offline-validation.json)的17项自写虚构字节案例通过，覆盖限量读取及脱敏；不是原生夹具、产品回归或微信测试。保留29份产品源码、24份历史脚本及288份旧证据。保存工具曾因旧清单混用path/cache_path失败，修正后通过；失败前未写新证据。

即使将来标记匹配，方向、初始同步/重连来源仍为unknown，不推广为普通来信准入，不连接模型/记忆/发送。[474](evidence/474-bounded-receive-proposal-checkpoint.json)保持产品0.1.22、自动回复关闭、监听保存停止状态；本轮没有进程/密钥/数据库/窗口/发送或Jev操作。最低已知额度剩余56%，id40保留。后续从475起；不要重复未更新候选审查或继续通用偏移扩展。

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

## 最新：现有接收代码可行性收敛（455–457）

2026-10-09（北京时间）。[455](evidence/455-minimized-source-feasibility.json)核对现有7类来源/组件、24处代码锚点。结论：**目前缺少具体采集器，不能靠连接现有监听、增加等待或开启配置实现最小化自动回复。** background只返回窗口绑定、最小化状态及行token/类型/文字；账号、方向、真实消息身份、历史与重连代次均无来源。selection是昵称前缀候选；ReadOnlyWeChatSource固定走visual_text，被原生最小化门拒绝；能力诊断始终拒绝准入。

monitor只统计并丢弃候选；CallbackInbox仅搬运调用方已构造的Event，不能生成身份依据或认证微信回调退出。Config与Engine仍只允许mock。451/452是静态关系，没有任何当前代码订阅这些微信内部事件。完整字段对应见[入站条件](INBOUND_ADMISSION.md)。**O1–O7及微信内部取消/计时字段仅适用于相应的进程内采集方案，不能扩展成所有来源都必须取得的条件。** 通用要求仍是账号/目标绑定、方向、消息去重与新旧规则、来源失效/停止，以及独立的目标绑定发送结果。

[456](evidence/456-minimized-source-validation.json)记录7组现有离线测试101/101通过，另有1个合成协议歧义示例与6个多余字段拒绝检查；29份产品源码未变，454列出的11个历史研究脚本未变。不是完整回归、原生夹具或微信运行验收。首次测试导入被自设审计拦截器阻止在Windows标准库ctypes初始化kernel32；初始化标准库后保留测试期拦截器，复跑通过且无外部执行尝试。非产品故障或工具自动审批拒绝。

[457](evidence/457-minimized-source-checkpoint.json)保存产品0.1.22、原监听停止、自动回复关闭；未调用Jev/其他判断模型，未操作窗口、读取进程/聊天数据库、加载目标DLL、重启监听或真实收发。额度最新已知剩余70%（primary用30%，secondary未知），40%监测继续。研究目录data/source-feasibility-20261009，后续证据从458起。

下一项只推进**具体采集器的端到端可行性方案**：先给出本机版本对应的读取入口、事件所有权、身份/方向/新旧判据、停止机制与离线验证办法，再实现隔离接收；来源不足就明确说明，不能以新增verified开关或继续堆叠内部偏移代替。现有普通个人号、免费、真正最小化目标不变；不再反复检查已排除的Web/Bot路径。任何新增运行范围应在具体方法可审阅之后另行处理，不能把当前静态授权扩大成进程或数据库访问。

## 最新：NewSync具体取消与超时闭包（451–454）

2026-10-09（北京时间）固定DLL磁盘只读。继续执行用户最新要求：**不调用 Jev，由助手直接判断；旧Jev要求已被覆盖。** [451](evidence/451-inbound-newsync-cancellation.json)直接绑定NewSync停止闭包9585188：捕获提交封装返回的task DWORD与同一service裸指针，经2eb0d20调用service+30。提交函数持有一个共享回调互斥量直到stop hook注册后才释放；完成闭包捕获并锁定同一个量。这是所选正常路径的关联，不代表所有竞态已解决。

停止函数35d970在adjusted service+8的bit0关闭时直接返回，不执行StopTask或映射清理；hook封装正常返回仍给true，pending promise可进入取消状态2。故取消状态2不证明底层停止已执行。响应路径先在锁内取出并移除wrapper，再解锁处理并调用回调；之后任务表查空也不证明没有已取出的回调。resolve1/cancel2共享pending0门，只防止该helper重复替换结果，不认证回调退出、对象寿命或消息新旧。

[452](evidence/452-inbound-newsync-timeout-lifetime.json)接通具体超时闭包9585228→5c1c0→所捕获job的+10=da4cc0；job构造链已核到9126068。所选取消工作向协程请求-1恢复；NewSync实际await路径在负恢复时取消promise并抛异常。上下文+48保存每轮原始timeout，+28继承定时服务；正常join/结果选择后才移除保存的注册句柄并释放shared job。373毫秒结论仍以具体looper匹配为条件，不能把120000写成已验收的整次120秒。移除超时句柄也不证明已出队回调退出。

本轮将观察条件分成取消请求、底层停止执行、映射移除、超时句柄移除、各回调退出及最终采集就绪；缺失项保持unknown，不能人工填verified。[454](evidence/454-inbound-cancel-validation.json)为同一执行者新鲜静态复核与20个纯值案例，非独立审查/并发/运行验收。450列出的11个历史脚本保持；研究目录data/inbound-cancel-20261009，后续证据从455起。

[453](evidence/453-inbound-cancel-checkpoint.json)保存监听仍停止，产品0.1.22、自动回复关闭，无可运行适配器。未操作窗口、重启监听、加载目标DLL、访问进程/数据库或真实收发；本轮模型判断调用为0。Codex最低可用窗口剩余71%（primary用29%，secondary未知），40%监测id40继续，不暂停主任务。

下一项转向**现有最小化接收代码与可采集字段的可行性核对**：逐项映射452条件，收敛具体采集方式和最小实现缺口，不再扩散存储层或重复通用取消反汇编。仍缺账号/方向/首批历史与重连代次、活跃实例和回调排空依据。静态链接通不代表已接入微信；真正最小化接收和受控发送验收仍在后续，自动回复最后按既定确认启用。

纯值案例覆盖promise状态0/1/2与service位0的组合、先resolve/先cancel的串行定值，以及旧cancel byte的bit0检查。没有使用真实客户端、网络、账号或聊天样本，也不是竞态复现。

## 最新：停止Jev参与；SyncKey更新与重置（447–450）

用户最新要求“继续，不要jev参加”：**停止 Jev 参与，由助手直接判断并继续工作；先前要求调用 Jev 的指令已被覆盖。** 下方Jev条目仅为历史记录，本轮及后续不再调用其判断，也不替换为其他外部判断模型。

2026-10-09（北京时间）继续固定DLL磁盘只读。[447](evidence/447-inbound-synckey-update.json)把2ea9360/2ef87d0绑定到micromsg.SyncKey/KeyVal：旧缓冲先解析，响应缓冲后解析，本helper确实检查两次解析结果。所选合并先保留旧列表每个key的首个value，再逐项以无符号较大值更新或插入响应项；旧列表后续同key不参与取最大。声明数量不一致只记录诊断后继续，输出数量改为合并集合大小。不同于444的外层解析返回丢失，不能把两层解析混为一谈。

普通响应为空时不修改缓存并返回0；旧缓冲为空时直接复制响应，不解析SyncKey，也返回0。合并失败-1/-3/-4产生空输出，2ea9360先将其写入owner+1a8，再交上层消费数值状态。下一请求经2ea6630读缓存/成员回退，若仍为空则构造实际长度1的零字节，再封装SKBuiltinBuffer_t。439中空/空比较仅为抽象条件，不代表这条正常请求构造会发空串；二进制零字节不等于空。

[448](evidence/448-inbound-synckey-reset.json)核所选后段：配置clicfg_xwechat_newsync_key_error_handle为false时，非零合并状态仍可保留处理器true；为true才返回false，且只对-1/-3显式清空并写回成员，-4不走该写回。只核调用的默认参数true，未读取实时配置。协议field1数值-2006直接替换响应字节并立即调用成员setter，发生在最终flush之前；不为其猜官方枚举名称。

getter4fac0与47220同取全局bb61c90的虚槽60；返回成员的380cc0/381550使用同一+400字符串及同一存储key地址。最终flush正常成功后另有成员写回，共同清理只清owner+1a8；下次可再次回退到成员。未认证活跃实例/账号一致性或持久写入成功。循环比较原请求与原响应，下一请求却可能采用合并值；循环继续不保证新状态进展，也不认证逐条消息新旧。

[449](evidence/449-inbound-buffer-checkpoint.json)保存监听仍停止，产品0.1.22、自动回复关闭，尚无可运行适配器。本轮没有调用Jev/其他判断模型，没有加载目标DLL、访问进程/聊天数据库、操作窗口、重启监听或真实收发。Codex可用窗口最低剩余74%（primary已用26%，secondary未知），40%监测id40继续；主任务未暂停。研究目录沿用本轮创建的data/inbound-buffer-20261008，文档时间按北京时间10月9日记。

[450](evidence/450-inbound-buffer-validation.json)记录同一执行者新鲜静态复核及31个纯值案例，非独立审查或运行验收；446列出的13个历史分析脚本保持。下一项绑定具体NewSync停止/取消闭包到已有服务取消链，明确排队回调寿命和可观测条件，不继续扩散存储内部。账号标识域/代次、方向、新旧边界及实际采集方式仍缺；随后才能形成最小接收实现，进行任务栏最小化接收与单好友受控发送验收，最后按既定确认开启自动回复。后续证据从451起。

复核涵盖固定DLL哈希、所选指令/跳转和RIP引用、SyncKey/KeyVal构造表与字段号、无符号比较、错误位掩码、配置分支、单零字节请求，以及旧脚本和保存监听状态未变。未运行产品、网络、原生、并发或回调排空测试。

## 最新：NewSync实际回调、解析返回与完成标记（442–446）

2026-10-08继续固定DLL磁盘只读。[443](evidence/443-inbound-newsync-result-producer.json)接通外层2ead5a0→2ead900→2eae7f0、内层job9584e78→2eaf5b0、future工厂9584f18→2eafdb0，以及提交wrapper9584fb8和完成回调9585048。wrapper内+a8是NewSyncRequest，+f8是NewSyncResponse；具体回调2eb0840经虚槽+20取得响应，再把响应与两个回调状态交给promise。复用355/364已核默认服务路径；未认证活跃实例、完整执行器和异步寿命。

两个回调状态A/B与协议response.field1分别保留，本回调不把协议field1替换成B。错误状态仍可正常resolve状态1，回调正常返回true；内层和外层任务均先发布结果，再置各自完成字1。完成字用于选择结果来源，不是解析成功、业务成功或历史排空标志。类型不匹配有异常路径，不能自动填0/0。

[444](evidence/444-inbound-newsync-parse-completion.json)直接绑定本NewSync封装解析器1070c40：内部694800会返回解析/必填/消耗输入的结果，但封装正常返回前强制AL=1，服务所查调用点也未检查该返回。此处不是把旧发送封装结论外推；仍未做异常网络运行复现，也不宣称上游所有校验都缺失。缺少parse_ok证据不能被完成字或非空响应对象补齐。

所选外层闭包传入重试预算0和原始超时参数120000。内层2ead900只在状态对非零、A为0或-110、剩余预算非零时等待并重试；因此该闭包默认不在这一层重试，不限制其他同步轮次或底层网络。构造的替代结果为A=-110/B=-1110和默认类型响应；完成字为0时读取经类型检查的context替代值。完整超时触发、取消/回调竞态及排空仍缺，不能把120000当作已验收的整次耗时。

[442](evidence/442-jev-result-decision.json)保留首次HTTP529失败及一次相同请求重试；成功返回jev-1.13.0，自动采用最高概率“实际响应生成”（0.73，confidence0.59），落实到443/444。失败调用无判断，不伪造用量。[446](evidence/446-inbound-result-validation.json)为同一执行者新鲜静态复核和纯值推演，非独立审查、运行验收；核验不重调API。

下一项核2ea9360/2ef87d0及-2006分支，接通响应缓冲向下一请求的更新、reset和重连边界，并补取消/回调寿命。方向、账号标识域/代次和具体采集方式仍缺。[445](evidence/445-inbound-result-checkpoint.json)保存监听仍停止；产品0.1.22、自动回复关闭，无可运行适配器。未加载DLL、操作窗口、重启监听、访问进程/聊天数据库或真实收发。额度本轮读取失败，最新值未知；上次成功读取为北京时间20:50监测的77%，不当作本轮数值，40%监测id40保留。441列出的12个历史脚本保持，新研究目录data/inbound-result-20261008，后续证据从447起。


本轮复核通过：27个函数区间、9个叶函数、35条直接边、6个表、209条指令观察、144条关键断言、24个纯值案例；12个历史脚本哈希保持，876个其他本地链接有效。纯值案例覆盖解析false仍被封装返回true、错误状态与promise/完成标记分离、重试预算0及错误种类、状态源选择和移位规则。保留529失败及成功请求，失败用量未知；没有运行产品、原生、网络、并发或回调排空测试。

## 最新：NewSync字段、继续循环与结束返回（437–441）

2026-10-08固定DLL磁盘只读。[438](evidence/438-inbound-newsync-fields.json)通过构造表、类型名和序列化字段号绑定NewSyncRequest/NewSyncResponse。请求field3和响应field4都指向SKBuiltinBuffer_t，循环使用其中field2字节串。该嵌套类型完整性只要求field1的presence，不要求字节串字段存在、非空或与field1数值一致。外层响应必填mask0xf也不能认证同步成功或历史边界。

[439](evidence/439-inbound-newsync-continuation.json)补所选正常循环：命令处理器返回true后，响应field3的低3个值位非零且请求/响应字节串不同，才继续；不同长度继续，相同空串停止，相同非空长度按实际长度做二进制比较。低位是字段值，不是presence。公式以对象有效稳定、插入的helper正常返回为条件，未证明完整CFG、并发别名安全或必然终止。

继续时当前输入mode改为6、首QWORD改为7，清理后重建请求；原始mode另存，循环结束后最终flush仍使用“原始mode==19”。因此后续请求mode6不等于已越过历史边界。处理器false会清成功标记并结束；普通低位耗尽或相同字节串结束则保留该标记。最终正常返回还受flush结果控制，true分支另有更新helper；正常结果分支都会reset批次管理器并清缓存字符串。循环停止、返回true、更新时间均不单独认证每条新消息或回调排空。

处理器的早期状态门允许响应field1数值0和-2006继续，不把-2006命名为未经认证的官方错误枚举，也不把该早期门当作完整成功条件。实际异步响应生产、解析失败/超时替代结果、响应字节串到下一请求状态的更新、重连/身份代次仍缺。

[437](evidence/437-jev-response-decision.json)保存一次真实Jev调用jev-1.13.0；按最大返回概率自动选“继续循环契约”（0.50，响应生产者0.49，confidence0.25），已落实到438/439。接近的概率只用于选工作方向。[441](evidence/441-inbound-response-validation.json)记录同一执行者的新鲜字节复核与纯值推演，非独立审查或运行验收；没有重调模型。

下一项补实际异步NewSync结果生产及解析/完成/失败路径，并接通响应缓冲到下一请求的更新与reset。保留逐条新旧/方向、账号标识域/代次、回调寿命及具体采集方式缺口。[440](evidence/440-inbound-response-checkpoint.json)保存监听仍停止，产品0.1.22、自动回复关闭，无可运行适配器。没有加载DLL、进程/聊天数据库访问、窗口操作、重启监听或真实收发。本轮Codex可用窗口最低剩余78%，40%监测id40继续有效；主任务未因额度规则暂停。436列出的12个历史脚本保持，新研究目录data/inbound-response-20261008，后续证据从442起。


复核重读固定DLL：15个函数区间、4个叶函数、10条直接边、3个表、186条指令观察、130条字段/分支断言、3个精确类型名、24个纯值案例通过；12个历史脚本哈希保持，841个其他本地链接有效。纯值推演覆盖低位耗尽、字节长度相异、相同空串、嵌入NUL、mode6与原始19区别、处理器/flush门和嵌套presence缺口。首次核验发现手写期望把3处RDX写成RAX，重读原字节后修正；字段映射和证据原始指令未变。所有推演都不调用目标DLL；未运行产品、原生、网络、并发或回调排空测试，未认证实际异步响应。

## 最新：同步模式19的来源与批次传递（432–436）

2026-10-08固定DLL磁盘只读。[433](evidence/433-inbound-sync-mode-source.json)接通构造表9584308、启动时捕获owner的闭包9584948+10→2eabce0、2eb19d0虚槽+28→2ea2f60。输入记录+8的mode来自所选通道接收结果；2ea2cc0以同一owner+60检查“保存值为零，或64位相减后的有符号差>=7201”，条件真则覆盖为19，假则保留输入值，包括原有19。因此19不是首次登录专属标志，非19也不认证单条新来信。

时钟调用已由PE导入表绑定GetSystemTimeAsFileTime，配合本地整数换算确定为整秒墙钟。正常有效值下门槛为7201秒，不是7200秒或单调计时；时钟回拨、越界返回-1及相减回绕须保留。API的UTC/100纳秒单位依据见[微软系统时间文档](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeasfiletime)及[FILETIME文档](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-filetime)，客户端门槛来自本地字节。

owner+60构造为零，所查driver在CoDoSync返回true的正常分支更新它，返回false的正常分支不走该处更新时间；busy/pending可触发再次处理。mode19前后设置/清除owner+1c8并发信号，但后置清除未检查driver返回AL。这些状态不是每条消息、完整同步成功或回调排空证明。

[434](evidence/434-inbound-sync-mode-propagation.json)将mode==19一路接到批次准备及后续闭包捕获。true/false准备分支都存在追加120字节元素的路径，并采用不同的时间调整调用/选项；没有在此处按mode整批拒绝。该mode与428的内嵌删除/清空过滤状态是两件事，不可直接命名is_history。调整helper完整语义、后续闭包处理及真实新旧边界仍缺。

[432](evidence/432-jev-sync-decision.json)记录一次真实Jev调用，模型jev-1.13.0；自动采用最高概率项“追mode生产者”（0.80，confidence0.70），已落实到433/434。原始建议保留，输入中10/100“预留容量”的推测仅按数值参数保存，不拿模型或该推测补二进制结论。[436](evidence/436-inbound-sync-validation.json)为同一执行者新鲜静态复核和纯算术推演，非独立审查或运行验收。

下一项补外层请求/响应的具体类型、低位/字符串继续循环条件和调用方结果；保留通道mode其他来源、账号标识域/代次、方向、回调寿命与具体采集方式缺口。[435](evidence/435-inbound-sync-checkpoint.json)记录监听仍停止，产品0.1.22、自动回复关闭，无可运行适配器。未加载DLL、操作窗口、重启监听、访问进程/聊天数据库或真实收发。本轮读取Codex额度剩余80%，40%保存监测id40继续有效；没有因该规则停止主任务。431列出的13个历史脚本保持，新目录data/inbound-sync-20261008，后续证据从437起。


本轮重读固定哈希DLL，核函数区间、直接边、虚表槽、RIP引用和导入目录，另核关键参数/阈值/传递断言。纯算术推演检查7200/7201边界、输入19保留、保存值0、墙钟回拨、64位回绕、FILETIME换算及driver状态组合；不执行目标DLL。Jev记录只验既有请求哈希、argmax、模型和用量，不重复API。未运行产品、原生、网络、并发或回调排空测试。

## 最新：批次过滤状态与控制参数（427–431）

2026-10-08继续固定DLL磁盘只读。[428](evidence/428-inbound-filter-owner-reset.json)绑定parent+1d0子管理器中的内嵌过滤状态+58；构造时阈值和active为零。rawtype51的选定控制路径可用操作15/16更新端点阈值，或用操作9的deleteMessages参数处理端点ID集合并启用过滤。2eb3780在active恰为1时按全局阈值、端点ID集合或端点阈值拒绝所选消息。所查外层正常flush的true/false路径都会清理集合并reset这份过滤状态；未认证异常、所有提前返回或重连阶段。

[429](evidence/429-inbound-clear-name-argument.json)核实clearAllMsg分支：name在rbp+190/R15，arg在另一字符串rbp+370；匹配名称后，230a20实际接收同一个name和默认值0。对稳定的clearAllMsg字节串，不论分类器跳过多长前缀，余下字符均非符号/数字或已耗尽，因此所查数字解析失败返回0。后续无符号old>=0跳过阈值和active写入，仍清除控制消息的append标志。这是有限静态参数不一致，不能写成运行复现，也不能据此断言所有过滤失效。

[427](evidence/427-jev-filter-decision.json)记录本轮一次真实Jev调用，返回jev-1.13.0；按用户要求自动选择最高概率项“核对名称/参数别名”（概率0.99，confidence0.98），已落实到429。模型的历史消息准入判断仍为未建立边界；选择概率不代替字节证据。

[431](evidence/431-inbound-filter-validation.json)记录同一执行者新鲜磁盘复核和纯值推演；[430](evidence/430-inbound-filter-checkpoint.json)保存监听仍停止。没有加载DLL、访问进程/聊天数据库、操作窗口、重启监听或真实收发。产品0.1.22、自动回复关闭，仍无可运行适配器。下一项查外层响应/同步阶段及数值mode19来源，补首批历史与重连边界；保留账号标识域/代次、回调寿命及可行采集方式缺口。不把active为零或reset当作“新消息已获准”。

用户新增要求：Pro额度剩余40%时保存进度。已创建本聊天的额度检查自动化（id40），每30分钟检查一次；创建时读到Codex周额度剩余83%。可读额度窗口中最低剩余不高于40%时，保存已核进度、未核改动与下一步，再通知；只提交/推送已验证的本任务改动。未知额度不按零处理，未要求停止主任务。检查有间隔，不保证恰好在40%触发。

426列出的13个历史脚本保持；新研究目录data/inbound-filter-20261008，历史证据不改，后续从432起。后续实质取舍继续实际调用Jev并自动采用返回的最高概率选项，不扩大已授权范围。


本轮只复核文件哈希、函数区间、直接边、RIP引用、28项操作表和关键字段/分支；纯值案例覆盖active关闭、全局/端点阈值、ID集合、reset以及clearAllMsg的全部12种前缀长度。Jev只复核既有返回、argmax和请求哈希，不重放API。完整解码不代表完整CFG、运行兼容或独立审查；未运行产品、原生或并发测试。

## 最新：账号字段与实际响应回调（422–426）

2026-10-08继续固定DLL磁盘只读。[423](evidence/423-inbound-account-field-origin.json)把result+88追到`UnifyAuthResponse`的field4账号段`AcctSectResp`，再到其field1字符串。42b160在输入两个DWORD状态均为零时写内部byte+4=1；另由响应field2的值bit1控制所选账号字符串复制。该值位与协议presence位不同，byte1不能单独认证有效身份。

完整性检查有明确缺口：外层账号段可缺省，账号段必填mask0x44也不包含field1的presence mask0x1。因此检查通过不要求这个字符串存在或非空。mode1还会用已有input+60覆盖result+88，标识域、活跃账号、身份代次和借用值寿命仍未认证，不能直接命名为已认证wxid。

[424](evidence/424-inbound-auth-response-callback.json)补实际响应对象及选定mode0回调：48c440构造共享UnifyAuthResponse；secmanualauth包装器内+c8为同一协议类型，回调经虚槽+20取得并复制到结果，随后resolve和替换上层共享响应。完成标记、promise状态1及回调返回true都不要求业务成功。这里只核选定路径，未认证整个混淆控制流、所有mode1替换或实时网络解析。

[422](evidence/422-jev-origin-decision.json)是本轮一次真实Jev调用，模型`jev-1.13.0`。按用户最新要求，每次返回后自动选概率最大的选项并继续；本轮最高为响应类型绑定（概率0.56、过滤状态0.43；confidence0.34），已落实到424；身份准入的最高项为保持未准入。概率与confidence分开保留，不把选择当作证据。Jev不代替字节核查、独立审查或微信回复模型。

下一项转到2eb3780过滤状态的具体归属、启用/reset与首批历史/重连边界；保留input+60来源、标识域/身份代次和采集方式缺口，不重复已绑定的默认类型与root成员赋值。[426](evidence/426-inbound-origin-validation.json)为同一执行者新鲜磁盘复核及纯值判据推演，[425](evidence/425-inbound-origin-checkpoint.json)保存监听仍停止。产品0.1.22、自动回复关闭，无可运行适配器；最小化接收、受控发送确认和最后开启自动回复仍待完成。

只向Jev提交抽象代码事实；密钥仅用于请求头，不入证据。未操作窗口、重启监听、加载DLL、访问进程/聊天数据库或真实收发。421列出的12个历史脚本保持，新研究目录data/inbound-origin-20261008；历史证据不改，后续从427起。


本轮验证重新读取固定哈希DLL，核完整函数范围/叶函数、原始rel32/RIP计算、类型表、两个protobuf字段跳转表和手写关键参数断言。纯Python值推演只覆盖已核presence/状态条件：账号field1缺失仍可通过选定完整性判据、状态0/0但field2值位关闭可跳过复制、完成标志可与错误状态共存。没有执行DLL，也不是产品或网络测试。

Jev记录只核请求哈希、模型、选项/概率、用量及凭据不入证据，不重复调用API。保存监听仍为stopped/native_reader_timeout、24569快照/24505最小化快照/unknown1，防待机不活动；保存值不是当前窗口认证。没有新增独立审查，静态完整解码不代表全控制流或运行兼容通过。

## 2026-10-08：418–421身份成员链与Jev记录复核

[421](evidence/421-inbound-identity-validation.json)重新读取固定DLL，核完整区间解码/哈希、两分支469a0等叶函数字节、原始rel32/RIP计算、两个类型表及关键参数/字段断言。重点验证全局root到task+2b8、两次记录复制、新成员+48字符串和root清空task+38。完整解码不等于整个CFG或业务语义已认证；当前只证明[419](evidence/419-inbound-root-member-source.json)所选路径。

[418](evidence/418-jev-identity-decisions.json)保留两次真实Jev请求/响应、模型与用量。校验请求哈希、选项有效性、记录一致性和密钥不入证据；不再次发送API请求。模型confidence=1也不证明二进制事实或接入已完成。第一次判candidate_unbound反映当时事实，之后才由419补绑定，不能倒改模型记录。

417列出的12个历史分析脚本哈希保持，七份文档本地链接、修改范围和git差异通过复核。[420](evidence/420-inbound-identity-checkpoint.json)的保存监听仍stopped/native_reader_timeout，24569快照/24505最小化快照/unknown1，防待机不活动；不是当前窗口认证。产品0.1.22、自动回复关闭。未运行产品、原生、并发或真实收发测试；无新增独立审查。

## 2026-10-07：414–417订阅链静态复核

本轮核固定DLL字节、完整解码区间、注册/派发字段、直接调用相对位移、RIP目标、调用表和有锚点叶函数，见[417](evidence/417-inbound-entry-validation.json)。特别复核同一getter707420、默认工厂到1799070、4a7360节点写入与17cac20字段对应、9d9ce0参数桥，以及4a7570的匹配/打标记。此为同一执行者静态复核，不是独立评审、产品测试、实机接收或兼容性通过。

[414](evidence/414-inbound-subscriber-registration.json)与[415](evidence/415-inbound-subscriber-dispatch.json)中的广范围函数仅选定指令语义经过分析，完整解码不等于完整CFG认证。MOV立即数扫描有分配大小等误报，只有手工追踪的注册进入结论；扫描未覆盖所有指令形式。部分磁盘标签并非明文，未将其猜译成业务名称。账号producer候选排除不能证明producer不存在。

413的8个旧分析脚本哈希保持；七份文档本地链接、git差异和修改范围已复核。[416](evidence/416-inbound-entry-checkpoint.json)保存监听文件SHA256仍为83ad7e3c3d8d26b99f4fdd9856fab9974e06e2a445c7873df26e44962df07f09，stopped/native_reader_timeout；24569快照、24505保存最小化快照、unknown1，防待机关闭。没有当前窗口认证。产品0.1.22、自动回复关闭，未运行产品/原生/并发或真实收发测试。

## 2026-10-07：410–413子任务与下层结果静态复核

本轮没有运行产品、原生、并发或真实收发测试。对固定哈希DLL重新读磁盘字节，复核22个完整解码的异常表区间、2个有锚点的叶函数、2张调用表、所选直接边/RIP位移及手工字段/分支断言；详见[413](evidence/413-inbound-storage-validation.json)。这是同一执行者复核，不是独立审查或运行兼容认证。

[410](evidence/410-inbound-child-dispatch.json)核缺对象跳过子任务、两类表共用调用体及结果返回。[411](evidence/411-inbound-storage-result.json)核空过滤true、下层map空true、非空`(acc&1)|byte`、byte恰为1的向量选择、缺键异常和上层结果传递。离线推演分别覆盖0/1混合结果、空结果、未归一化byte和跳过任务；仅验证所选分支算术，不执行DLL，不制造数据库结果，也不证明完整事务语义。

历史409列出的10个脚本哈希保持。当前七份文档的本地链接与差异范围复核通过，历史证据保留；[412](evidence/412-inbound-storage-checkpoint.json)保存监听文件哈希仍为83ad7e3c3d8d26b99f4fdd9856fab9974e06e2a445c7873df26e44962df07f09，停止原因native_reader_timeout，24569次快照/24505次保存最小化快照/unknown1。没有当前窗口认证，未重启监听。产品0.1.22、自动回复关闭。

## 后端分组与两层汇总静态复核（406–409，2026-10-07）

[406](evidence/406-inbound-backend-groups.json)记录数值tag分组、外层等待/返回map和output+40；[407](evidence/407-inbound-result-aggregation.json)记录两类任务表、组内汇总与额外派发入口。[409](evidence/409-inbound-backend-validation.json)重新核固定DLL哈希、选定函数完整解码、原始rel32/RIP算术、表槽、字段/分支断言及文档链接。确切计数以409为准，同一执行者，无独立审查；405列出的10脚本保持。

离线投影覆盖tag0/1/2和无符号边界、空汇总、全非零及混合组结果，并区分部分返回组与总标志。这只检验所选条件和算术，不执行目标代码、数据库或真实消息，不证明完整控制流、事务回滚、逐条成功或无其他通知。

扫描仅检查指定指令形式和unwind归属；完整e8候选与增加REX前缀筛选的f8候选范围不同，均非穷尽对象引用。静态表探针对表后的字符串/数据产生的非代码值未作为虚槽采用。实际订阅者未定位，构造/析构不能代替注册。历史writer仅提取graph/save定义，未执行旧顶层或重写历史证据。

[408](evidence/408-inbound-backend-checkpoint.json)只核保存监听文件，仍停止且哈希不变；未检查当前窗口、操作电源、重启监听、进行产品/原生/并发测试、加载DLL、访问进程/聊天库/密钥或发送。0.1.22、自动回复关闭，观察方案未执行。

## 入站检查和通知包装路径静态复核（402–405，2026-10-06）

[402](evidence/402-inbound-consumer-gates.json)记录零ID分流、第二个键容器、可选handler及追加赋值；[403](evidence/403-inbound-group-notification.json)记录结果分组和回调包装。[405](evidence/405-inbound-notification-validation.json)重新读取固定DLL，核完整选定函数区间、叶函数、原始rel32/RIP算术、表槽、字段/分支断言及文档链接。确切计数以405为准；401列出的8个历史脚本哈希保持。同一执行者，无独立审查。

离线投影只检验选定gate的跳过/继续分支和字段偏移，不能模拟完整消费者、后端或事件交付。零ID、空handler、Text gate=true、结果bit0、正常returntrue、executor提交均不得单独认证真实来信。

研究扫描最初因未显式导入RSP/RBP常量失败，已补导入；不是产品失败。474c0同偏移写入候选实际是输出对象，未当root生产者。aba560最初叶探针超出128字节范围，随后改读完整所属函数；其未经完整业务认证，不用于宣称a7cd20对raw1无操作。历史writer只提取纯graph/save AST，未执行旧顶层或改旧证据。

[404](evidence/404-inbound-notification-checkpoint.json)确认保存监听文件哈希不变且仍停止，不代表当前窗口检查。未重启监听、操作窗口、电源、进程/密钥/聊天库、真实收发或运行产品/原生/并发测试。0.1.22、自动回复关闭，O1–O7未执行。

## 普通批次、端点键及默认descriptor静态复核（397–401，2026-10-06）

[397](evidence/397-inbound-batch-consumer.json)保存批次/时间/过滤链，[398](evidence/398-inbound-key-root-filter.json)保存键选择与root成员间接来源，[399](evidence/399-inbound-default-descriptor.json)保存选定默认descriptor。[401](evidence/401-inbound-owner-validation.json)重新核固定DLL哈希、完整函数解码、精确表目标、指令与原始rel32/RIP位移算术；具体去重计数以401为准。396列出的11个历史脚本保持，同一执行者，无独立审查。

离线条件投影分别检验扩展构造的低32位/乘1000、前置阈值比较及端点选择；不执行客户端，不覆盖后续时间调整、完整过滤策略或真实来信。选定默认descriptor的常量返回也不等于整个客户端最终对象不变。静态条件路径已接到实际批次消费者，但实际账号、历史边界和最终事件仍未验收。

研究探针对无unwind的469c0误用window后改用leaf，随后将469a0两条返回分支完整纳入46字节证据；aba980也纳入两条返回共43字节。不是产品失败。追加检查发现2eb9af0还能重写扩展+70，报告明确限制初始化公式；没有把它作为最终时间不变量。仅从旧writer提取graph/save AST，未导入/运行其顶层，历史证据保留。

[400](evidence/400-inbound-owner-checkpoint.json)只核保存监听状态，仍停止；未操作窗口、重启监听、执行产品/原生/并发/网络测试、访问进程/密钥/聊天库或发送。0.1.22、自动回复关闭，观察方案未实施。

## 入站AddMsg与字段来源静态复核（393–396，2026-10-06）

[393](evidence/393-inbound-addmsg-dispatch.json)保存9区间、2叶函数、89观察；[394](evidence/394-inbound-field-provenance.json)保存8区间、71观察。[396](evidence/396-inbound-contract-validation.json)重新读取固定DLL并复核范围哈希、完整解码、直接rel32/RIP算术、精确表目标、15组字段号/偏移，以及两段原始MOVABS重叠重建的`micromsg.AddMsg`。静态复核通过：17区间、2叶函数、16直接边、1表、160观察、94字段/分支断言、5指定表目标、560本地链接。前轮392列出的6个脚本哈希保持；同一执行者，无新增独立审查。

4个presence mask案例只核必填位条件，包含字段12缺失但必填位齐全；不包含所有嵌套/流检查，不是完整parse_ok或客户端执行。元素步长统一明确为0x70（112）字节，避免把十六进制误读为十进制70。普通type1入队与另一向量消费者身份仍未闭合，全区间解码也不是完整CFG/实机可达认证。

研究中排除了下载请求的msgsvrid、报告字段issendmsg和另一紧凑记录的IsSender作为实时方向证据；未把邻接AddBypMsg名称的下一张表误当其自身表。短AddMsg类型名需从立即数恢复，字符串扫描漏报不是无该类型。猜测的旧writer文件名不存在后按实际清单读取，只AST提取纯helper，没有执行旧writer或改历史证据。

[395](evidence/395-inbound-contract-checkpoint.json)只核原监听保存文件，仍停止，非当前窗口检查。本轮无产品/原生/并发/网络测试、DLL执行、进程访问、真实收发或观察方案实施。产品0.1.22、自动回复关闭。

## 最终结果与上层再次调用静态复核（2026-10-06）

[389](evidence/389-send-text-final-notification.json)记录6区间/83观察；[390](evidence/390-send-upper-reentry-result.json)记录10区间/4叶函数/73观察。[392](evidence/392-send-text-final-validation.json)新读固定DLL，核16区间、4叶函数、23直接边、2表、156观察、110字段/分支断言、3指定表目标，复算rel32/RIP位移并核信号诊断。前轮6脚本哈希不变，同一执行者复核，无独立审查。

7个上层再次调用判定案例、3个空值案例、2个本地结果案例均为指令条件的离线推导：包括原始type1拒绝、type49/subtype6或130满足其他条件后允许，以及所选state不为2分支保留整体0/0却写本地state5。没有执行目标指令、模拟网络或复现发送故障。全区间解码/哈希不等于完整CFG或运行可达；最终对象类别改变也不代表所有分支已追完。

两处猜测证据名称按实际清单修正，最终检查了引用存在性。无unwind的小getter/setter和分类函数按直接调用锚点补叶函数，分类包含两个ret，未把第一次ret当整个函数结束。历史脚本只AST取纯helper，未执行旧writer顶层或改历史证据。

[391](evidence/391-send-text-final-checkpoint.json)只读保存的停止状态，仍stopped/native_reader_timeout；不认证当前窗口。未跑产品/原生/并发/网络测试，未操作窗口、启动监听或发送。[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)仍未实施，产品0.1.22、自动回复关闭。

## 文字重试与响应消费静态复核（2026-10-06）

[385](evidence/385-send-text-retry-budget.json)记录10区间/63观察，[386](evidence/386-send-text-response-consumer.json)记录4区间/1叶函数/40观察，含共享文字函数和共同调用点。[388](evidence/388-send-text-result-validation.json)去重后新读固定DLL，核对13区间、1叶函数、8直接边、4表、102观察、68字段/分支断言、6指定表目标和6个推导重试案例；复算位移、核对计时callable/诊断、默认参数、正常回边及限定消费区间。前轮8脚本哈希不变，同一执行者复核，无独立审查。

推导案例是基于已核分支的离线布尔/计数检查，不执行客户端或模拟网络，不当作重试、取消、超时或送达实测。文字全区间解码仍不是完整CFG认证。一次误入字符串探针的无效地址被只读节断言拒绝，随后按实际RIP引用查询，没有放宽到可写节或活跃进程。历史脚本/证据保持原样，新validator只复制通用校验文本，不执行旧writer顶层。

[387](evidence/387-send-text-result-checkpoint.json)保存监听仍stopped/native_reader_timeout；只读停止文件，不认证当前窗口。未跑产品/原生/并发/网络测试，未加入适配器重试或发送。[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)仍未实施，自动回复关闭。

## 文字处理器注册与请求静态复核（2026-10-06）

[381](evidence/381-send-handler-registry.json)记录15区间/78观察，[382](evidence/382-send-text-request.json)记录8区间/4叶函数/83观察。[384](evidence/384-send-target-validation.json)新读固定DLL，核对23区间、4叶函数、123条直接边、5表、161观察、62项字段/分支断言及5个指定表目标；复算RIP/rel32、从只读字节和立即数重建Text/Location名称、确认options两DWORD差异，前轮8脚本哈希不变。同一执行者复核，无独立审查。

关键解释修正：旧具体候选现在确认为Location，另找到Text入口；362中位置函数的响应消费不外推文字。注册插入有重复key保留已有值分支，不能把默认注册当活跃类型证明。文字约65KB区间全部解码，但只追部分构造/调用，不能据此声称全分支验证。一次叶探针把多余的size参数当另一地址，正确输出33字节叶函数后在额外地址断言失败；一次手写复核期望把捕获源寄存器rbx写成rax，按真实指令修正后重跑通过。这些是分析工具/期望值修正，非产品测试失败。

[383](evidence/383-send-target-checkpoint.json)仅复核保存的停止状态。未访问运行进程/窗口、加载DLL、执行产品/原生/并发测试或发送；[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)仍未实施。静态类型与字段进展不等于最小化文字收发已接通。

## 上层scope与停止边界静态复核（2026-10-06）

[377](evidence/377-send-scope-origin.json)记录24区间/5叶函数/84观察，[378](evidence/378-send-scope-shutdown.json)记录11区间/1叶函数/42观察。[380](evidence/380-send-scope-validation.json)重新读取固定哈希DLL，验证35区间、6叶函数、36直接边、8表、126观察、77项字段/分支断言与10个指定表目标；另复算RIP/rel32位移、同一协程局部key、析构诊断和停止次序。前轮9脚本哈希不变；核对文档链接与改动范围。同一执行者复核，无新增独立审查。

探索用的直接边、虚槽、LEA和指针扫描仅发现候选，不能从无命中推断无调用者，也不能从指针命中证明活跃类型。研究中一次表探针把第二地址误作数量参数、两次猜测旧证据名失败，按工具参数和实际文件名修正。停止接口初步解释混用了主对象表，复核355子对象调整后明确改为`8fa5398+0 → 3575d0`；没有把主服务析构当已调用。叶函数47310核对了两分支直到最终ret。以上均为分析工具/解释修正，非产品故障。

[379](evidence/379-send-scope-checkpoint.json)只读保存的停止状态；没有访问活跃进程或窗口。未运行产品/原生/并发/真实网络测试，也没有真实消息进入模型、记忆或发送。[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)仍未实施；静态复核通过不等于运行适配器可用。

## looper构造、时钟和取消静态复核（2026-10-05）

[372](evidence/372-send-looper-assignment.json)记录11区间/1叶函数/30观察；[373](evidence/373-send-looper-clock.json)记录8区间/39观察；[374](evidence/374-send-looper-cancel-dispatch.json)记录14区间/4叶函数/52观察，包含重复节点。内容为具体构造赋值、毫秒换算、闭包派发与取消顺序；不是实机计时或并发测试。

[376](evidence/376-send-looper-validation.json)重新读取固定DLL，核对区间/叶锚点、原始相对位移、表、导入符号、选定字段与分支，检查纳秒到毫秒的整数换算及有限静态顺序案例，保存前轮7个脚本哈希、文档链接和改动范围。仅同一执行者复核，无新增独立审查。字段位移扫描可能匹配无关结构且遗漏无异常表叶函数，未把扫描命中当作赋值证据；TLS setter最终使用直接调用锚点。早期writer未导入/重跑，仅提取两个纯helper定义；历史脚本与证据保持不变。

[375](evidence/375-send-looper-checkpoint.json)仅检查停止文件，未访问进程或窗口。没有产品改动、产品/原生测试、运行计时/并发/网络测试、真实模型记忆或发送；[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)仍未实施。120秒只在所查具体实现条件下成立，不宣称实际发送时间。

## 执行器、计时参数与生命周期静态复核（2026-10-05）

[367](evidence/367-send-executor-resume.json)记录12区间/3叶函数/36观察；[368](evidence/368-send-timeout-parameter.json)记录11区间/2叶函数/36观察；[369](evidence/369-send-lifetime-boundaries.json)记录9区间/1叶函数/33观察。节点有重叠，不将相加数视为不同函数总数。内容是条件调用关系、线程检查、原始数值传递、正常清理及join限制，不是执行器或超时运行验收。

[371](evidence/371-send-executor-validation.json)重新核对固定DLL哈希、区间和叶锚点、原始位移/表、导入符号、数值与分支、历史脚本哈希、文档链接和改动范围。同一执行者复核，无独立审查。研究探针对无异常表的TLS短函数先返回NO_UNWIND_START，随后按直接调用锚点解码；叶探针遇jmp提前结束的job thunk沿既有分支锚点核对完整14字节，不虚构异常表范围。复核脚本首遍断言后在汇总阶段因source变量未定义失败，补明确路径后重新完整复核；不是产品/原生测试失败。没有产品改动或故障注入。

[370](evidence/370-send-executor-checkpoint.json)仅只读停止文件，保存状态哈希供复核；没有操作窗口、进程、监听、电源、模型或真实记忆。[观察方案](ISOLATED_OBSERVATION_4_1_15_50.md)未实施。产品仍0.1.22，无产品/原生/异常网络/竞态或真实发送测试，旧369项通过不外推本轮。

## 逐条响应、解析与回调桥静态复核（2026-10-05）

[362](evidence/362-send-response-items.json)记录7区间/1叶函数/1直接边/2表/44观察；[363](evidence/363-send-response-parse-failure.json)记录6区间/3直接边/2表/34观察；[364](evidence/364-send-callback-registration.json)记录7区间/4叶函数/5直接边/3表/31观察。包含重叠节点，不把相加数视为独立函数数。结论涉及字段布局、单消息首条消费、解析返回覆盖与默认回调注册链。

[366](evidence/366-send-response-items-validation.json)保存固定DLL哈希、完整解码、叶函数锚点、指令/表/独立位移算术、选定分支及文档范围复核；同一执行者，无新增独立审查。研究探针给无异常表的短方法时返回NO_UNWIND_START，后按已有调用/表锚点单独解码；不存在据此补造异常表边界。部分初次文档读取使用了错误目录并报文件不存在，随后在wechat-memory-ai/docs读取；不属于产品失败。

[365](evidence/365-send-response-items-checkpoint.json)只读保存状态仍停止，最小化字段仅最后观察。产品仍0.1.22，未运行产品回归、原生测试、异常网络响应或真实收发；旧369项结果不外推。完整边界见[兼容性报告](SEND_COMPATIBILITY_4_1_15_50.md)。

## 响应与取消静态复核（2026-10-05）

[358](evidence/358-send-response-promise-contract.json)记录13区间/2叶函数/10直接边/3表/45观察；[359](evidence/359-send-cancel-timeout-contract.json)记录15区间/2叶函数/7直接边/7表/44观察，两份包含重叠节点。核查任务映射、结果状态优先级、promise pending转换及停止hook。未执行微信候选，不把静态反汇编当作运行或竞态测试。

[361](evidence/361-send-result-validation.json)保存固定哈希、范围/指令/表/位移、选定状态分支及文档的同一执行者复核。探索探针曾遇无异常表叶函数断言、手工参数拼写错误、只读字符串约束拒绝；证据生成首遍又因叶函数长度少算1字节停止，核对实际指令长度11字节后修正。没有因此放宽边界或运行客户端，失败仅属于研究辅助脚本；详细记录在361。

[360](evidence/360-send-result-checkpoint.json)原监听保存状态仍停止，未恢复窗口/重启。产品仍0.1.22，无产品回归、13项原生测试、独立审查、真实模型记忆或发送；旧369项结果不外推。结果判定限制见[报告](SEND_COMPATIBILITY_4_1_15_50.md)。

## 协程与任务号静态复核（2026-10-05）

[354](evidence/354-send-coroutine-dispatch.json)记录32区间/2叶函数/27直接边/3选定表/35指令观察；[355](evidence/355-send-service-task-return.json)记录13区间/3叶函数/16直接边/3选定表/38观察。两份材料有重叠，不把相加数宣称为不同函数总数。查明await协程要求、捕获回调关系、服务来源，以及本地任务号和提交布尔值分离；没有运行候选发送或证明完整执行器路径。

[357](evidence/357-send-dispatch-validation.json)对固定磁盘哈希、解码区间与指令、表指针、直接边rel32单独算术、选定RIP引用及文档链接做同一执行者复核。没有独立人员审查、产品/13项原生回归；旧369项通过不外推。本轮临时分析文件曾命名inspect.py遮蔽标准库，造成Capstone导入NameError，改名后恢复；没有产品改动。

[356](evidence/356-send-dispatch-checkpoint.json)只读保存监听状态仍停止。未加载执行微信DLL、读进程内存/密钥、恢复窗口、重启、连接真实模型记忆或发送。完整结论和剩余条件见[报告](SEND_COMPATIBILITY_4_1_15_50.md)。

## .50 离线反汇编验证（2026-10-05）

[349](evidence/349-offline-disassembler-tool.json)固定隔离Capstone依赖；[350](evidence/350-decoded-send-anchor-references.json)记录76原始位移候选中的41解码引用、旧地址的指令边界；[351](evidence/351-send-candidate-callgraph.json)记录28解码区间、28直接边、6有另外锚点的叶函数候选、3类型表、16条指令观察与7字段关系。是静态研究，不是运行兼容或发送测试。

[353](evidence/353-send-disassembly-validation.json)重新校验模块/工具哈希、28区间和28边、类型表、SIMD位移的单独算术复核、字段证据及文档链接。未跑产品回归/原生测试、独立人员审查或微信框架；旧369项结果不扩张为本轮结果。工具分析库在临时目录执行过，不能笼统声称本轮没有执行任何第三方代码；Weixin.dll未加载、微信进程未读写。[352](evidence/352-send-disassembly-checkpoint.json)保存监听仍停止，未操作窗口或发送。详细证据与未解析间接调用见[报告](SEND_COMPATIBILITY_4_1_15_50.md)。

## .50 磁盘静态兼容性核查（2026-10-05）

[343](evidence/343-disk-client-pe-compatibility.json)记录本机EXE/DLL版本、哈希、PE节与旧RVA对照；[344](evidence/344-send-compat-public-refs.json)记录公开refs及额外固定头文件；[345](evidence/345-disk-send-literal-anchors.json)是公开字面量与有限字节扫描结果，未找到可调用入口。[346](evidence/346-disk-pe-crosscheck.json)通过第二种实现复核两个哈希/版本与10个代码位置的异常表区间，同一执行者，不是独立人员复审或实机运行测试。

[347](evidence/347-send-compat-checkpoint.json)保存原监听仍停止；[348](evidence/348-send-compat-static-validation.json)核对来源常量、JSON结构、链接及文档提交范围。详细局限见[SEND_COMPATIBILITY_4_1_15_50](SEND_COMPATIBILITY_4_1_15_50.md)。本轮临时脚本只读磁盘文件，未加载DLL/读进程内存；未安装分析依赖或运行第三方候选。产品仍0.1.22，未重跑回归/13项原生/安装测试，既有369项结果不扩张为本轮兼容认证；无真实模型、记忆或发送。

## 扩展非 UIA 发送静态核查（2026-10-05）

[339](evidence/339-non-uia-expansion-manifest.json)固定新增5仓库46份公开文本与树元数据；[340](evidence/340-hook-static-traces.json)保存上一ID去重、零ID正文前缀、129条覆盖128槽、超时后完成以及先出队再发送的静态推演。它们不是执行第三方代码、性能测试或本机微信复现。具体结论见[NON_UIA_SEND_AUDIT](NON_UIA_SEND_AUDIT.md)。

[341](evidence/341-non-uia-expansion-validation.json)记录新旧固定文件哈希/大小、固定源码行号和文档链接检查；仅主执行者自查，无新增独立复审。[342](evidence/342-non-uia-expansion-checkpoint.json)再次读取保存状态仍stopped/native_reader_timeout，未重新探测窗口或重启监听。

本轮仅文档和脱敏证据变化，源码仍v0.1.22。未重跑产品回归/安装/原生测试，369/369是321/322的既有结果，13项原生继续排除。没有候选安装、导入、编译、执行、密钥读取、客户端注入或写入、真实模型/聊天记忆/发送。静态核查没有使任何候选获得本机准入。

## 个人号目标确认与只读故障调查（2026-10-05）

[338](evidence/338-web-login-user-result.json)保存用户手工检查反馈：可登录但网页版不支持使用。作为当前Web候选未形成可用通道的依据，非程序独立验证；没有消息收发、真实模型或聊天记忆验收，也不外推全体账号。

[337](evidence/337-web-login-policy-block.json)记录用户授权后的首次官方登录页打开尝试：cua_repl/iab被站点安全策略拒绝，未进入自动审批，未观察二维码、未验证账号资格。已请求用户自行操作并反馈结果，没有技术绕过或第三方执行；这不是微信登录失败测试。

[335](evidence/335-personal-route-timeout-power.json)以停止runtime.json的文件时间限定System/Kernel-Power查询，只保留事件ID、相对毫秒和进入/退出待机布尔标记。16分钟窗口仅见507，扩大4小时后找到506；进入至退出1062083ms，退出距停止文件1637ms。不能推导精确调用起点或待机触发原因。再次读取公开状态仍停止，24569成功快照、24505最小化、unknown1；没有改电源/重启/操作窗口。此轮只改产品决定与文档，没有运行产品回归或任何原生/第三方测试。

## 非 UIA 静态评估（2026-10-05）

[333](evidence/333-non-uia-checkpoint.json)最终只读状态发现原监听已超时停止：24569成功快照/24505最小化、unknown1，第24570次调用首次超时，外层745786ms/原生completed745479ms。防待机请求不再活动；未归因待机、未重启/操作窗口。不能沿用329的活动结论。

[332](evidence/332-non-uia-static-validation.json)核对47份哈希/大小及固定源码/本地文档链接；[334](evidence/334-non-uia-review.json)独立复审无实质错误，未运行代码或访问实机，3个Wechaty网页条款未由复审者独立联网验证。

[331](evidence/331-non-uia-source-manifest.json)记录5仓库47份公开文本的固定SHA/文件哈希，全部下载后核对大小与哈希。[评估报告](NON_UIA_ROUTE_AUDIT.md)中的同序号分页、游标先保存等例子是静态推演，本轮没有新功能测试或第三方运行验证。没有产品修改，未重跑回归/安装/原生测试；321/322的369项结果不作为本轮新结果。没有登录、读取本机密钥、客户端修改、真实模型、聊天记忆或发送。

## 免费来源规则反例与现有守卫复核

[330独立复审](evidence/330-source-audit-review.json)8份公共源文件哈希/大小与326一致，12项离线检查通过，代码规则投影及文档范围无剩余发现；未执行第三方代码/网络/原生/UI或访问真实数据、监听。329原监听只读检查仍活动9326次/9262次最小化、unknown1、0超时、防待机开启。

[326](evidence/326-source-route-audit.json)只保存两公共仓库的固定提交、8文件哈希及源码位置，获取源码时访问公开GitHub；第三方源码未安装/导入/运行，也没有操作微信。[离线脚本](experiments/check_source_assumptions.py)仅使用虚构输入和本项目纯Python会话，不是第三方完整仿真；[328](evidence/328-source-countermodels-final.json)的8个反例和4个本地守卫共12检查通过，证明所投影规则的局限以及本地仍拒绝晋升，不是适配器通过。演练本身不联网，没有模型、真实记忆或发送。

[327](evidence/327-source-countermodels.json)保留初稿1失败/2错误：前端淘汰演练只有1个锚点，不满足至少2个连续锚点；另误期望ReadError包含详细原因，而实际通过report返回。修正演练输入与断言后328通过，产品源码和阈值未改。没有重跑完整回归/安装，13项原生夹具继续排除。固定来源的判断及限制见[SOURCE_ROUTE_AUDIT](SOURCE_ROUTE_AUDIT.md)。

## 最小化入站元数据检查

[324独立复审](evidence/324-inbound-review.json)确认异常整数修复与正文读取范围说明准确，14项纯Python测试通过、无剩余发现；未另做原生/UI、配置/真实数据、监听或外网调用。全回归/安装/实机结果仅核对保存证据。325最终状态：原监听活动1670次、1606次最小化，当前最小化，unknown仍1、0超时、防待机请求活动，未重启。

[312](evidence/312-inbound-capabilities-red.txt)新增14项因接口缺失先失败；[313](evidence/313-inbound-capabilities-targeted.txt)与后台读取、恢复、绑定、窗口状态共39项通过0.076秒。覆盖严格字段/类型/计数、元数据不是准入、空列表/到底仍拒绝、协议不能进入消息会话、绑定必须先存在、绑定变化拒绝、元数据变化不自动重试。

[314](evidence/314-live-inbound-capabilities.json)保留首次实机探测未进入读取的编译失败；[315](evidence/315-inbound-native-build-failure.txt)定位为不存在的AutomationElement.Compare，改用相等运算符后[316](evidence/316-live-inbound-capabilities.json)取得3次最小化结果。第一次探测脚本还先发生一次monitor状态函数名导入错误，未执行原生调用；编译诊断初次输出解码也失败，随后315完整保留编译错误。没有用重试成功抹掉失败。

自查及独立审查发现超大整数百分比经math.isfinite会抛OverflowError；[319](evidence/319-inbound-large-percent-red.txt)保留复现。改为直接检查有限范围，巨型整数/NaN/Infinity均固定ReadError。最终[321](evidence/321-inbound-final-regression.txt)/[322范围](evidence/322-inbound-final-scope.json)：**382中选369/369通过，36.625秒，0失败/错误/跳过**，原NativeProbeTests、NativeOcrCheckTests、NativeVisualTextTests、VisualBitmapTests共13项继续排除，不称全套通过。317/318是补异常整数前的首次369项结果37.079秒。

[320最终原生检查](evidence/320-live-inbound-final.json)在先确认祖先路径到达绑定根、再查询祖先属性的修订后，再次3/3最小化成功。每次8行含5文本，5文本都有AutomationId但全行仅1个非空ID；辅助属性/TextPattern/子控件均0，列表到窗口根8节点均无ScrollPattern；耗时343/329/343ms仅为诊断单次耗时，不是来信延迟或后台回复验收。绑定获取使用现有background在内存读基线正文后丢弃，不能把整个过程称作从未读正文；三次诊断本身只读元数据。未输出/保存正文、绑定或截图，没有UI操作、模型调用、真实聊天记忆或发送。

[323](evidence/323-inbound-package.json)离线构建安装24模块、5原生资源、3入口帮助通过，安装源码逐字节相同，模块和发行包版本均0.1.22，临时目录清理。没有安装外部依赖或读取个人配置/.env，没有网络/原生/UI执行。之前模块__version__滞后于发行版的问题同步修正。

原监听未重启，仍运行v0.1.21和防待机；320检查点活动1376次/1312次最小化，unknown仍1、0超时。新报告不接monitor/Engine，真实收发方向、联系人认证、历史和消息身份均未完成，详见[入站准入](INBOUND_ADMISSION.md)。

## 自动回复检查与受控最小化新增文本

[305](evidence/305-auto-reply-offline.json)离线回调演练10项检查通过；[306](evidence/306-auto-reply-targeted.txt)/[307范围](evidence/307-auto-reply-targeted-scope.json)12个相关模块 **157/157通过，12.029秒，0失败/错误/跳过**。覆盖生成、有限记忆、去重/自身/历史过滤、目标变化、暂停、结果不明拦截、模型协议和只读来源边界。HTTP仅本机夹具，记忆为临时虚构数据；未读个人配置或.env，没有外部模型、真实聊天记忆或微信发送。原4类13项原生继续不跑，不称全套回归；此次没有产品代码改动，不重复离线安装。

[308](evidence/308-auto-reply-listener-check.json)前后状态：272→281快照，208→217最小化，未知文本0→1，0超时。[309](evidence/309-minimized-new-text-observed.json)另记用户对本轮请求明确回复“已发送”；探针本身无法读取用户输入，308未保留最初脚本硬编码的confirmation=false，而指向309，快照保持原样。区间9次全部最小化，证明受控发送期间捕获1个新增文本；没有记录/匹配正文，不验证发件身份/方向/历史或端到端延迟。监听与防待机持续活动，无重启或窗口操作。

检查结论见[AUTO_REPLY_CHECK.md](AUTO_REPLY_CHECK.md)：模拟流程可用，真实自动回复尚未连接，不能仅改开关启用。下面304及更早0新增记录不覆盖本次观察。

[310独立审查](evidence/310-auto-reply-review.json)仅阅读源码、测试、文档和已保存证据，没有另跑测试/查询监听或访问原生/UI/真实模型。未发现违反现有模拟/只读约定的新缺陷，文档无剩余发现；明确真实准入/桥接/发送缺失，is_current不是发送许可。305–309的157项测试和新增文本计数仅复核证据，不冒称独立实测。

## 按用户要求启用防自动待机

后续[304检查点](evidence/304-keep-awake-minimized-checkpoint.json)：95次快照、31次最小化，当前minimized=true，0新增/超时；监听及防待机请求均活动。303之后窗口变为最小化，没有通过工具操作或重启。此结果覆盖下文303的较早窗口状态，不等于新来信或实际防待机效果验收。

[301](evidence/301-before-enable-keep-awake.json)保存启用前4442次快照（4400次最小化）和0新增状态；[302](evidence/302-enable-keep-awake.json)正常停止后在同目录以开启选项启动最终v0.1.21，首基线不回放。[303](evidence/303-keep-awake-enabled-checkpoint.json)活动27次，0新增/超时，防待机申请与活动标志均true；27次全部非最小化，没有操作窗口。只确认申请及运行状态，不代表实际防待机、最小化新来信或自动回复验收。没有产品代码变更，未重复运行测试、API模型、聊天记忆或发送。

## v0.1.21 待机证据与可选电源请求

[284](evidence/284-standby-timeout.json)记录v0.1.19监听2266次全最小化后停止，0新增；第2267次外层耗时1806710ms并超时，原生completed2791ms。脱敏Windows事件表明待机持续1804219ms，退出比停止状态早2932ms。只确认本次调用跨过待机，不确定原生完成与待机的绝对先后，不归因旧259，也不将无发送确认的零新增视为来信失败。

[285](evidence/285-keep-awake-red.txt)新增10项因缺少API/字段而失败；[286](evidence/286-keep-awake-targeted.txt)联合34项通过，补正常停止/活动状态、非Windows与实际PowerShell转发后，[287](evidence/287-keep-awake-targeted-final.txt)43项通过。测试替换电源调用，覆盖默认off、申请失败先于Reader、读取失败/正常停止释放、先前线程状态恢复、释放失败保留既有错误、旧状态/畸形值和隐藏子进程参数传递。

首次366项中选353通过36.895秒（288/289），290离线安装通过。独立审查随后发现Python调用入口把字符串`"false"`当成启用且写入状态；CLI的布尔开关不受影响。现三个入口在任何电源/文件/进程操作前拒绝非bool。[293](evidence/293-keep-awake-invalid-red.txt)保留首次复现：新增监控测试遗漏电源mock，两个truthy子例短时调用了本机申请/释放，Reader/Popen仍被替换；修正夹具后，[294](evidence/294-keep-awake-invalid-mocked-red.txt)全mock重现相同失败，[295](evidence/295-keep-awake-fixed.txt)修复后45项通过。

最终368项中选 **355/355通过，36.912秒，0失败/错误/跳过**：[296](evidence/296-keep-awake-final-regression.txt)、[297范围](evidence/297-keep-awake-final-scope.json)。仍排除原4类13项原生夹具，没有重试被拒MSAA/合成位图。[298最终离线安装](evidence/298-keep-awake-final-package.json)23模块/5原生资源逐字节匹配，3入口帮助通过，无配置/网络/原生/UI执行，临时目录已清理。

[291](evidence/291-power-request-lifecycle.json)为本机电源API瞬时申请和释放成功；没有修改电源计划或附加屏幕常亮，未验证实际防待机效果。[292](evidence/292-standby-listener-start.json)显式新启动v0.1.21普通后台监听，首快照最小化、0新增、最慢诊断有效，防待机仍off。旧故障证据保留，首视口只作基线。没有模型/聊天记忆/发送；新来信、长期稳定及自动回复仍未验收。

[299检查点](evidence/299-keep-awake-monitor-checkpoint.json)新监听活动、241次全最小化、0新增/超时，最高414ms，旧3处监听均停止。工作进程启动于Python参数严格校验补丁之前，其CLI参数为有效bool，当前路径不受该补丁影响；未为加载此检查打断基线。未收到发送/睡眠操作确认，不据此推断不存在来信或睡眠原因。

[300独立复审](evidence/300-keep-awake-review.json)43项通过4.081秒，非bool问题修复后无剩余代码/文档发现。完整回归、安装和监听检查点仅复核上述证据，未另跑真实电源/原生/UI、模型或操作监听。文档明确293夹具遗漏及API成功不等于防待机效果；没有将本次证据扩展为新来信、旧259原因或自动回复通过。

## v0.1.20 最慢子调用阶段保留

最新发现353项，选定 **340/340通过，321.639秒，0失败/错误/跳过**：[279](evidence/279-slowest-read-regression.txt)、[280范围](evidence/280-slowest-read-regression-scope.json)。继续排除原4类13项原生夹具，不称全套通过；未重试被拒MSAA/合成位图。

新增6项先因缺少slowest_call失败：[275](evidence/275-slowest-read-red.txt)。实现后联合45项通过：[276](evidence/276-slowest-read-targeted.txt)。自查补出畸形父级最大耗时误归零的具体失败：[277](evidence/277-slowest-invalid-parent-red.txt)，修复后13项通过：[278](evidence/278-slowest-read-corrected.txt)。覆盖较快调用不抹去慢阶段、更慢替换/同值保留、失败/超时、固定大小与独立复制、旧状态和嵌套白名单。不改变原生C#、期限/绑定/重读或消息接受。

[274](evidence/274-minimized-arrival-watch.json)是在已活动且最小化的1837次基线之后请求一条新普通消息的旁观记录。120.140秒内采得32个不同子调用，2.603–3.218秒，中位2.809秒；当时最高6768ms不在该采样内，无法追溯其阶段。结束时1900次快照全部最小化、0新增/超时，尚未收到发送确认，故保留等待，不能说来信成功或失败。旁观程序结束没有停止监听。

[282](evidence/282-slowest-monitor-checkpoint.json)检查点：活动监听仍是v0.1.19，2073次快照全部最小化、0新增/超时、最高6961ms，发送确认未收到。v0.1.20只更新源码，不在等待期间重启；slowest_call显示null，不追补旧最慢阶段。旧259超时没有复现，不能声称根因已定位、性能已改善或新来信已验收。

[281离线安装](evidence/281-slowest-read-package.json)版本0.1.20，22模块/5原生资源逐字节匹配、3入口帮助通过；只复制源码/README/构建声明到临时目录，无个人配置/.env读取、无网络/原生/UI执行，临时目录已清理。

[283独立审查](evidence/283-slowest-read-review.json)45项通过，并验证极值诊断状态1752字节及多层字典复制隔离。代码没有发现；两项文档表述经修正复审，最终没有遗留问题。文档区分了历史不请求输入与本轮已请求，以及诊断不含正文与读取器仍在内存读正文。审查只复核完整回归、安装和运行检查点的已有证据，没有另跑原生/UI/API或访问活动监听。没有真实模型调用、实际聊天记忆写入或微信发送。以下为历史结果。

## v0.1.19 后台时序与恢复边界

最新发现347项，选定 **334/334通过，75.767秒，0失败/错误/跳过**：[269](evidence/269-reader-timing-regression.txt)、[270范围](evidence/270-reader-timing-regression-scope.json)。继续排除原4类13项原生夹具，不称全套通过，没有重试被拒MSAA/合成位图。

[264](evidence/264-reader-timing-red.txt)为新增7项因缺少诊断接口而失败，不声称当时已验证每项业务断言；[265](evidence/265-reader-timing-targeted.txt)定向60项通过，包括真实Python子进程的超时管道读取、失败阶段保留、畸形记录脱敏与旧重读期限。没有原生UI/位图夹具。[267](evidence/267-background-recovery-boundaries.txt)新增4项验证既有恢复保护，均通过；同绑定重读保留旧会话检查点，失去锚点为终态，重启基线不回放，自身/同步历史/未知均不能提升为来信。

[266](evidence/266-background-native-timing.json)为现有产品Scoped NativeReader实际编译/运行，5次非最小化快照，0候选，0.803–1.071秒。随后Computer Use两次最小化按钮操作均报`coordinate input geometry is unavailable`，未确认成功；用户手动最小化后，新时序监听原生状态才确认最小化。[268](evidence/268-minimized-timing-sample.json)90.937秒采样取得48个不同子调用，0.706–1.357秒、中位0.8555秒；采样结束148次快照全部最小化、0新文本、0超时。阶段外时间包含未观测的启动/调度/结束，不能全部归为启动成本。

[272](evidence/272-timing-monitor-checkpoint.json)检查时新监听仍活动，285次快照全部最小化，0新文本/超时，旧两处监听均停止。保留新监听以收集后续失败阶段，继续前先查状态。259旧超时本轮未复现，根因未确定；本轮未请求新消息，未观察到新文本，因此不是到达、方向或长期稳定验收。

[271离线安装](evidence/271-reader-timing-package.json)版本0.1.19，22模块/5原生资源逐字节匹配，3入口帮助通过。仅复制源码/README/构建声明到临时目录，未读取个人配置或.env，无网络/UI/原生执行，临时目录已清理。

[273独立审查](evidence/273-reader-timing-review.json)58项定向通过，无代码发现。两处文档表述已修正并复审：重启只保证跳过已可见基线；未观察到新增不等于证明没有消息到达。最终无剩余代码/文档发现。审查没有运行原生/UI/API或操作活动监听；包与实机结果仅复核已有证据。本轮没有真实模型调用、实际聊天记忆写入或微信发送。详细语义与范围见[READER_TIMING.md](READER_TIMING.md)。以下为历史结果。

## v0.1.18普通窗口后台文本

最新发现336项，选定 **323/323通过，76.531秒，0失败/错误/跳过**：[260](evidence/260-background-final-regression.txt)、[261范围](evidence/261-background-final-regression-scope.json)。继续排除原4类13项原生测试，不能称全套通过。

[255](evidence/255-background-read-red.txt)新增7项先7失败0错误；[256](evidence/256-background-read-targeted.txt)联合48项通过，涵盖基线不回放、两条相同文本、全部unknown、其他协议拒绝、绑定变化与旧组合拒绝、同绑定有界重读、期限后不交付和状态不含正文。

[254](evidence/254-minimized-arrival-incomplete.json)：旧多选监听6755次后window_or_list_changed，0候选；用户确认操作过窗口，恢复检查已有两条文字，但不能算捕获成功。[257](evidence/257-background-monitor-start.json)普通模式可启动；[258](evidence/258-background-minimize-transition.json)操作窗口时连续性丢失，随后原生检查仍minimized=false，不能算最小化转换。[259](evidence/259-background-minimized-timeout.json)准确最小化后另一常驻运行3927次，0新文本，最后native_reader_timeout；当前已停止。它证明最小化静态文本可读，不证明来信捕获、长期稳定、方向/身份或后台发送。

[262离线安装](evidence/262-background-package.json)一次构建/隔离安装通过：版本0.1.18，22个模块和5个原生资源逐字节匹配，3个入口及后台模式帮助通过。未读取个人配置或.env、未执行原生/UI/模型/实际记忆/发送，临时目录已清理。

[263独立审查](evidence/263-background-review.json)选定67项纯Python测试通过（1.561秒），另核验4096容量拒绝的计数原子性和后台协议不能进入准入；代码及最终文档均无待修复发现。未运行原生/UI/API，真实最小化来信、恢复、身份/历史及发送不在其验证范围。提交前再次查询确认两处监听均已停止。

没有调用模型、写实际聊天记忆或发送。原4类13项原生夹具继续排除。以下为旧阶段记录。

## 常驻只读与多选模式

最终发现329项，选定 **316/316通过，38.000秒，0失败/错误/跳过**：[250](evidence/250-listener-final-regression.txt)、[251范围](evidence/251-listener-final-regression-scope.json)。继续排除NativeProbeTests、NativeOcrCheckTests、NativeVisualTextTests、VisualBitmapTests共13项，不称全套通过，未重试被拒MSAA/合成位图。

225/227/231保留常驻、诊断和脚本入口的RED；226/228/232为对应定向通过。此前302项回归通过记录234/235仅覆盖多选模式加入前。236独立审查17项通过，其范围也止于当时。多选模式239先8项失败，240含相关测试33项通过；最小化切换实机241停止后，新增有界重读，242保留2失败1错误。243的46项中隐藏子进程启动一次返回3，245单项复跑通过但具体原因未确定，不能删除该失败。

增量审查发现Windows状态读取阻止原子替换可使监听停止；用真实临时文件读句柄及假Reader确定性复现，247三项2失败1错误。修复为最多20次替换、累计请求等待至多190ms（不含I/O和调度），持久失败保留旧完整状态并清理临时文件。248联合61项通过7.218秒。另一项非文本ControlType复核缺口以SelectionRow保存并比较实际type.Id修复。249收尾独立31项通过1.145秒，无剩余确认缺陷；没有执行原生/UI/网络/模型。

实机范围：229首次最小化元数据采样没有取得最小化样本，保留未完成；230三次最小化仅布局计数可读。233原视觉模式最小化按守卫拒绝，237正常窗口隐藏启动/状态/停止通过。241新增多选在最小化切换时前后不一致停止，不能算通过；244已最小化启动后58次基线，246停止时115次基线与新启动均零候选。253最终C#实际编译运行三次最小化快照（16行、11文本）基线交付0，并确认visual仍报window_minimized；读取器已关闭。未调用Engine/模型/记忆/发送，未保存正文、昵称、绑定或截图。**真实最小化新消息仍待验收**；这些基线不能证明方向身份或后台回复。

[252离线安装](evidence/252-listener-package.json)一次构建/隔离安装通过：版本0.1.17，22模块和5原生资源逐字节匹配，3个已安装入口帮助通过。没有个人配置、.env、聊天记忆、原生运行或网络/模型调用，临时目录已清理。

协议/范围见[CONTINUOUS_LISTENER.md](CONTINUOUS_LISTENER.md)。以下为历史阶段的测试记录。

最新执行日期：2026-10-03（Asia/Shanghai）；以下历史阶段另有2026-10-01/02记录。Windows 11 家庭版中文版 build 26200，Python 3.12.14，SQLite 3.53.1；PowerShell 5.1 和 7.6.5。

## v0.1.16 之后的只读实机补验（产品代码未变）

[223](evidence/223-bound-source-window-stop.json)：配置900秒上限，实际39次快照后因`window_minimized`停止，标记尚未建立、候选0、源已关闭。验收脚本虽然退出0，语义结果未完成，不能按成功处理；稍后的用户发送确认只表示已发送，不能证明旧监听捕获到达。

[224](evidence/224-bound-source-self-and-incoming.json)：恢复并最大化同一测试窗口后，新建显式绑定来源，3次基线返回0；新的来信标记建立边界后，1条真实新自身消息判为self且不交付，随后1条真实新来信交付一次。已交付候选关闭前`is_current=true`、关闭后false。共103快照、154.297秒、退出0，源已关闭。诊断包装只旁观既有联合会话返回的观察值，不改分类、过滤、连续性规则或阈值；没有保存正文、标记、绑定、身份或截图。

这次补验没有调用模型、导入Engine/SQLite/记忆或发送。真实重取为0；只证明受监督、不翻历史、当前最大化窗口中的这一组事件，不证明身份认证、任意历史同步、服务器消息ID、跨重启去重或长期运行。未修改产品代码，未重跑已有回归套件或13项排除的原生测试；此前失败证据保留。

## v0.1.16 有限日常偏好与自然管理

发现297项，最终选定执行 **284/284，31.078秒，0失败/错误/跳过**：[220](evidence/220-natural-memory-final-regression.txt)、[221范围](evidence/221-natural-memory-final-regression-scope.json)。继续排除NativeProbeTests、NativeOcrCheckTests、NativeVisualTextTests、VisualBitmapTests共13项，未重跑被拒夹具，不能称全套297项通过。220/221还保留首次284/284、32.430秒的结果；随后将三个既有测试的仓库示例加载改为显式虚构凭据，避免顺带读取本机.env，再执行最终复验。该调整只影响测试夹具，没有更改产品凭据加载行为。

新增15项服务测试，验证三个主题的有限完整句式、来源/持久化、预检无写、同值幂等、唯一旧别名更新、歧义/类型冲突/容量拒绝、命名管理、未知查询、会话隔离、重启和最新遗忘账本下旧备份不复活。缺少observe时预期失败：[215](evidence/215-natural-preferences-red.txt)，15项含4个断言失败及45个缺失方法错误子项；实现后与既有Memory/MemoryRecall共 **44/44，2.598秒**：[216](evidence/216-natural-preferences-targeted.txt)。216头部外部计时2.594秒与runner计时来自同一轮。

新增10项Engine集成测试先出现8个预期断言失败、0错误：[217](evidence/217-preference-engine-red.txt)；实现后 **10/10，0.966秒**：[218](evidence/218-preference-engine-targeted.txt)。验证当前用户陈述进入同一轮模型上下文且只调用一次、过滤/身份/暂停/预算拒绝不提取、歧义/容量澄清不占模型预算、重复事件不重写、模型失败保留已接受事实、助手输出不形成偏好，以及配额耗尽后的本地纠正/遗忘/查询。测试使用直接Config、临时Store与假模型，不读取实际密钥。

[219独立审查](evidence/219-natural-memory-review.json)无代码发现；修正了一处文档过度承诺，不将全文规则说成能理解玩笑/反讽。独立复验37/37、2.790秒，另3项临时边界检查通过，覆盖金额预算、敏感混合文本和额度用完后的本地管理。它没有重复全回归，也没有读取实际配置或密钥。

[222离线安装](evidence/222-natural-memory-package.json)一次构建/安装通过：版本0.1.16、21个Python模块源码匹配、5个原生资源、两个已安装CLI帮助，以及三个主题各六阶段共18项临时Store验证。仓库草稿仅在临时目录读取，保持fake/off且无凭据；模型与socket调用均0，临时目录已清理。草稿不在wheel中。

本轮没有新增真实API请求、实际微信访问、真实聊天记忆或发送。支持范围仅饮品、咖啡加糖和回复长度；额外结构不匹配时不提取，恰好等于支持句式的玩笑/反讽仍可能保存。无法据此认为任意事实理解、自然度或真实微信自动回复已经通过；此前206质量失败保留。具体表达和失败语义见[NATURAL_PREFERENCES.md](NATURAL_PREFERENCES.md)。

## v0.1.15 真实模型评估与有限饮品回忆（历史记录）

发现272项，选定执行 **259/259，155.633秒，0失败/错误/跳过**：[209](evidence/209-memory-recall-final-regression.txt)、[210范围](evidence/210-memory-recall-final-regression-scope.json)。210外部计时155.641秒为同一轮；继续排除NativeProbeTests、NativeOcrCheckTests、NativeVisualTextTests、VisualBitmapTests共13项，没有重跑被拒夹具，不能说全套272项通过。

真实API评估共8次，仅使用临时隔离数据库内的虚构对话。首6次[204](evidence/204-live-model-synthetic-evaluation.json)技术成功，中位1.369秒、最慢2.390秒，覆盖接话、Engine重新实例化后偏好、纠正、遗忘及详细回答；Engine重建不等同于操作系统进程重启。明确记忆/纠正/遗忘命令各0次模型调用，实际请求上下文验证旧值移除。风格审查[205](evidence/205-live-model-style-review.json)为助手审查，非用户验收。

调整提示后再请求2次[206](evidence/206-live-model-style-follow-up.json)，技术成功但质量失败：无记录时编造饮品偏好，下一轮又声称删除该虚构偏好。8次总范围0.697–2.390秒，为模型完整请求的小样本耗时，不是微信端到端测速、稳定P95或自然度通过。真实API测试已经停止；没有再次付费调用以掩盖失败。所有临时库已清理，未读取微信、写真实聊天记忆或发送；主配置未覆盖，本机评估配置与密钥被Git忽略。

随后新增12项有限饮品回忆测试：完整问句与4个键别名、仅当前会话active/explicit/preference、忽略助手历史/摘要、空记录与歧义不调用模型、纠正/遗忘及Store关闭重开、跨会话隔离、查询不修改结构化偏好、推荐/引用/混合请求沿原路由。首轮11项有18个预期失败子项、0错误；审查发现删除A而保留B时状态措辞误指旧记录，再补第12项先失败后修复，均保留于[211](evidence/211-memory-recall-red.txt)。[212](evidence/212-memory-recall-targeted.txt)保留首轮49/49及最终联合既有Engine/Memory **50/50，19.750秒**。

[213独立审查](evidence/213-memory-recall-review.json)复验12/12、4.582秒及2项额外边界检查，1项发现已修复、剩余0。新分支只陈述当前保存记录，不推断缺失等于删除、不把单条偏好提升为最爱；普通推荐、其他主题与复杂问法仍可能走模型，不能推广为所有个人信息均不猜测。自动偏好提取仍未实现，Engine照常保存模拟回复历史。

另补固定`truncated`审计原因白名单，任意外部字段仍脱敏；2项审计回归先失败[207](evidence/207-audit-truncated-red.txt)、再通过[208](evidence/208-audit-truncated-targeted.txt)。提示仅增加不解释内部处理和不无端断言用户从未说过的要求；最大合法persona系统提示962字符，小于1000字符预留，206已证明提示本身不足以保证事实正确。

[214离线打包](evidence/214-memory-recall-package.json)一次构建/隔离安装通过：版本0.1.15、20个模块源码匹配、5个原生资源、两个已安装CLI帮助及临时Store中4项饮品核对通过。模型/网络/原生/UI调用均0，未读取实际.env或个人配置，临时目录清理。仓库草稿仅复制到临时目录核验fake/off，不在wheel中。以上没有改变自身新事件、真实源交付和自动回复仍未通过的边界。

## v0.1.14 DeepSeek适配与自然聊天提示（历史记录）

最新发现258项，选定执行**245/245，43.862秒，0失败/错误/跳过**：[201](evidence/201-deepseek-final-regression.txt)、[202范围](evidence/202-deepseek-final-regression-scope.json)。202外部单调时钟43.859秒与runner使用的时钟略有差异，为同一轮。继续排除原4类13项原生测试，未重跑被拒夹具，不能说258项全套通过。

新增8项请求/配置测试，验证DeepSeek精确非思考载荷、输出上限映射、异常终止及非空推理/工具响应拒绝、过长回复不截断交付、网络显式开启/凭据/官方端点约束、未激活草稿。197首次7失败和2个测试subTest作用域错误；修正测试后仍有15个失败子项、0错误，证明功能缺失，随后实现。定向21/21通过10.375秒：[199](evidence/199-deepseek-contract-targeted.txt)。请求仅发往loopback假服务，未调用真实DeepSeek。

自然聊天提示使用既有Engine/Memory38项验证（198），未添加只镜像提示词的测试。最长合法persona时系统提示908字符，小于既有1000字符预留；模型失败用例补入truncated，确认空回复、不发送、不自动重试。200独立审查及21项定向复验通过，无待修复发现。

[203离线打包](evidence/203-deepseek-package.json)一次构建/安装通过；20个Python模块、5个原生资源、安装版本0.1.14和两个CLI帮助正确。将仓库草稿复制到临时目录，以安装版配置加载器验证：默认fake/网络关闭；只有虚构凭据仍未开启；虚构凭据和两个显式开关齐备后才可解析DeepSeek。没有HTTP、原生/UI或实际模型/记忆调用，临时目录清理。草稿为仓库文件，不在wheel中。

上述测试不能证明真实云API可用、模型自然度或实际延迟。现有个人配置未覆盖；本机仅创建空密钥占位文件，不在Git中。微信自身新事件/真实源交付等未验证边界保持下述记录。

## v0.1.13 显式绑定消息源与有界重取（历史记录）

最新发现250项，实际选定执行 **237/237，58.384秒，0失败/错误/跳过**：[194](evidence/194-source-final-regression.txt)、[195范围清单](evidence/195-source-final-regression-scope.json)。195的外层单调时钟为58.390秒，与194为同一轮。仍排除4类13项原生测试（NativeOcrCheckTests 4、VisualBitmapTests 3、NativeVisualTextTests 2、NativeProbeTests 4），不是完整250项通过；未重跑此前被拒夹具。

新增43项纯Python测试：共享来信过滤新增1项，连同既有预检共14项通过[178](evidence/178-shared-filter-targeted.txt)；显式绑定8项先失败[179](evidence/179-bound-reader-red.txt)、再通过[180](evidence/180-bound-reader-targeted.txt)；消息源24项先失败[181](evidence/181-source-red.txt)、再通过[182](evidence/182-source-targeted.txt)；重取10项先失败[190](evidence/190-resample-red.txt)、再通过[191](evidence/191-resample-targeted.txt)。覆盖绑定输入验证与防御性复制、首次私有管道约束、来源生命周期/线程/期限/候选失效、关闭拒绝，以及仅对已绑定联合读取的瞬态变化重取。失败证据中的本机绝对路径已脱敏，失败结果保留。

`ReadOnlyWeChatSource`为库级封装，要求调用方提供expected_binding，首次原生读取前即检查同一窗口实例；沿用每次新标记准入。没有接入Engine、模型、SQLite/记忆或发送。已绑定联合读取只对原生`visual_snapshot_changed`最多尝试3次子调用，共享原8秒单调时钟预算和同一Python会话检查点；其余错误及首次未绑定读取不重取。[192](evidence/192-binding-source-review.json)独立审查无待修复发现，绑定与重取18项纯Python联合复验通过；不代表真实重取恢复已验证。

| 实机证据 | 结果与范围 |
| --- | --- |
| [177](evidence/177-live-preflight-incoming-pass.json) | v0.1.12预检369次快照，完整标记批次丢弃1文本，之后2条来信候选达到目标、关闭并退出0。正向准入通过；旧data日志已完成，不再是等待会话。 |
| [183](evidence/183-live-self-listener-timeout.json)、[184](evidence/184-live-self-filter-component.json)、[185](evidence/185-self-sample-direction-check.json) | 第一次自身监听99快照后超时、无候选；随后样本3次判incoming，目视核查确认它实际在左侧，并非自身样本，不能记为自身验证。 |
| [187](evidence/187-live-self-filter-inconclusive.json)、[188](evidence/188-live-self-visual-reasons.json) | 真正自身到达期间31快照后以`visual_snapshot_changed`停止、无新增，验收未通过。后续联合检查为unknown，另次纯视觉读取显示`edges_inconsistent`；两次读取不构成原子诊断。 |
| [189](evidence/189-live-maximized-self-component.json) | 最大化后已可见自身消息3/3判self，共享过滤返回0。只验证历史消息组件，未验证新自身事件到达或已解锁会话中的过滤；分类阈值未改。 |
| [193](evidence/193-live-bound-source-baseline.json) | 显式绑定消息源三次基线零交付、关闭后poll/send拒绝、错误窗口绑定拒绝通过；没有验证该封装中新候选实际交付。 |

真实自身新增过滤、消息源新候选交付及真实重取恢复仍缺证据；任意历史同步、锁屏/RDP与长期可靠性也未全面实测。没有可信到底信号，祖先滚动条诊断暂缓；当前只限同一授权窗口、有人监督且不翻历史。所有原验证/模型/发送标志保持false。[186](evidence/186-local-model-configuration-presence.json)仅确认现配置为fake模型、网络关闭且无模型名称/端点；用户自然聊天偏好是后续需求，不是模型已选定或已调用。

v0.1.13离线打包及临时安装验证通过：[196](evidence/196-source-package.json)。前两次构建退出1，诊断发现输出路径长266字符；改用data内更短的受控临时路径后，第3次构建/安装退出0。确认20个Python模块、5个原生源码资源、安装版本0.1.13、两个已安装CLI的帮助及3种缺失绑定拒绝（NativeReader调用0次），临时目录已清理。未执行原生程序、访问UI或用户配置、调用模型或写入记忆；前两次失败仍保留。

## v0.1.12 真实双消息、历史负例与只读准入（历史记录）

1005监听真实到达验收通过：[159](evidence/159-live-1005-arrivals.json)，1028次接受快照、2条incoming候选、1次复用token，目标完成退出0。该会话启动于v0.1.10，没有在升级时替换基线。v0.1.11重新启动及窗口恢复的两个会话各连续3次均返回0（160/162）。最小化以`window_minimized`、历史上翻及一次实际最大化布局变化以连续性丢失停止（161）；错误码3，停止前均无候选。最初误将最大化当作最小化的操作另列，未虚报成功。

163近底部历史负例停止；164更早历史起点下移却产生2条旧文本候选（均unknown）。因此增加`PreflightSession`，把UI出现候选与可供只读预览的标记后incoming分开。171在同样历史路径重验：底层2候选，准入返回0、未解锁。没有在此次负例中发送新消息、调用模型、写记忆或保存图片。

新增13项纯Python回归覆盖历史形状（含incoming变体）、基线/随机标记、完整标记批次丢弃、末条/单条/方向检查、重复文字、永久丢弃自身/unknown、绑定/连续性失败、停止/完成关闭、CLI有界等待与数量语义、中文JSON在ASCII重定向下可用。165为缺失实现预期失败；166初12项通过；169独立审查新增编码用例失败；170修复后13/13通过0.013秒。独立审查[172](evidence/172-preflight-review.json)无未修复发现。

最终发现207项，实际执行**194/194，26.399秒，0失败/错误/跳过**：[173](evidence/173-preflight-final-regression.txt)、[174范围清单](evidence/174-preflight-final-regression-scope.json)。仍有意排除原4类13项原生夹具测试，不能称全套207项通过，也没有重跑此前被拒的动作。167/168保留ASCII修复前的193项结果；两份计时分别来自unittest与外部单调时钟，存在微小差异，计时以原始runner输出为准。

v0.1.12离线构建与临时安装验证版本、preflight模块、原生源码资源和已安装CLI帮助，未访问网络或微信、未编译原生程序，临时目录已清理：[175](evidence/175-preflight-package.json)。失败记录165/169的本机绝对路径已脱敏，原始异常与行号保留。

当时正向准入尚在等待受控输入；[176](evidence/176-live-preflight-pending.json)只保存不含实际验证文字的基线与阶段快照。随后[177](evidence/177-live-preflight-incoming-pass.json)已完成本轮新标记及两条后续来信的正向准入，旧会话已关闭。没有用旧1005文字解锁新会话。所有原验证标志保持false；纯Python过滤回归不能替代尚缺的实机项目，最新结果见顶部。

## v0.1.11 视觉诊断及空证据恢复

新增5项Python协议回归，检查11原因×3方向×2类型的66种组合、输出字段/零计数、私有值隔离、非法原因/次数、纯诊断与正文协议隔离。定向9/9、0.002秒见[152](evidence/152-visual-gates-targeted.txt)。148为新增原因前预期失败，149为首8项通过。

本轮有意排除4个原生测试类共13项；发现194项，实际执行的 **181/181，25.073秒，0失败/错误/跳过**，见[155](evidence/155-visual-recovery-regression.txt)和逐项排除清单[156](evidence/156-visual-recovery-regression-scope.json)。这不是完整194项验证。缺失客户端/PowerShell等其他回归仍执行。此前被自动审批拒绝的原位图夹具未重跑；151另保留一个新增纯值策略夹具缺少实现的编译失败，没有执行该夹具，随后移除且未重试。原生重取耗尽、重取中的窗口/行变动尚无故障注入测试。

实际产品读取器编译和只读诊断成功。实现前150为12次中一次5条头像不确定；153细分后为30次中一次5条前景证据全零，**153尚未启用重取**。实现后[154](evidence/154-live-visual-recovery.json)60次全部5来信候选/1几何未知，59次一次捕获、1次两次捕获恢复。只验证当前测试窗口，不证明底层根因或全面稳定。纯诊断没有读取Name、保存图像/正文或接入模型/记忆/发送。

独立源代码审查无待修复发现，范围与限制见[157](evidence/157-visual-recovery-review.json)。当时1005原长监听没有重启，仍使用v0.1.10；随后已完成并退出，见159，不再视为活动监听。

v0.1.11离线构建/临时安装后，版本、两个C#源码资源、重取源码打包、已安装Python诊断协议及临时清理通过，[158](evidence/158-visual-recovery-package.json)。该包检查没有编译/执行原生读取器或访问微信；实际源码产品读取见154。

## v0.1.10 等待目标数量与明确完成原因（历史记录）

最终 `python -X utf8 scripts/test.py`：**189/189，37.232秒，0失败/错误/跳过**，[145](evidence/145-listener-wait-final-suite.txt)。此前增加正数等待上限/数量目标的完整187项为50.433秒，[142](evidence/142-listener-wait-full-suite.txt)；随后增加显式零秒持续等待的两个回归。

新增9项覆盖基线/空白/非文本不计数、相同文本各自计数、三个模式整批接受、超时与目标完成原因、默认30秒、错误/中断清理、非法参数在创建读取器前拒绝，以及双PowerShell入口3600秒参数。139为预期失败；140保留测试误用既有计数字段名称的失败，纠正后141为7项通过。持续等待先失败[143](evidence/143-listener-until-target-red.txt)，实现后[144](evidence/144-listener-until-target-fixed.txt)为9/9、1.806秒。

独立初审7/7、2.700秒，无待修复发现；审查者随后实现零秒增量，由主任务复核并执行189项完整回归。审查与限制见[146](evidence/146-listener-wait-review.json)。本轮视觉波动诊断仅依据代码/已有证据；另一次独立诊断尝试的合成位图编译执行被自动审批拒绝，未执行或重试，不计入测试通过数。

v0.1.10临时离线构建/安装后核验版本、C#资源、CLI帮助与零秒无目标的拒绝；临时目录清理通过，[147](evidence/147-listener-wait-package.json)。这次包检查没有编译或执行原生读取器，也没有访问真实微信。

实机1003/1004监听均已到时结束且新增0，之后可见测试文字不能补记成到达事件；1004视觉方向四次有明确/未知波动，见[138](evidence/138-late-live-inputs.json)。随后另起基线的1005持续等待已完成，见159，忽略目录data中的日志为历史记录。所有验证标志仍false；未调用模型、写入记忆或发送。

## v0.1.9 联合候选与方向可见性（历史记录）

现有Python执行 `python -X utf8 scripts/test.py`，最终 **180/180，33.600秒，0失败/错误/跳过**：[134](evidence/134-visual-occurrence-final-suite.txt)。先前联合版本178/178、34.004秒见[129](evidence/129-visual-occurrence-full-suite.txt)，随后补入两个未知方向转变回归并修复，未覆盖原始结果。

新增12项最终 **12/12，0.646秒**：[133](evidence/133-visual-unknown-transition-fixed.txt)。包含实际编译C#行值比较、缺失客户端清理、协议/模式隔离、正文重复而方向不同、旧组合重现不能用方向绕过、方向冲突/未知桥接、批次计数与CLI脱敏。127缺失实现预期失败，132未知转变失败，128为首10项通过。

独立审查10项初审与12项补审通过；补审另查27种三次方向序列、4096上限、拒绝批次不提交方向证据/计数/历史。无待修复发现，见[135](evidence/135-joined-review.json)。完整真实UIA内容变动没有由新夹具模拟，不把纯值比较测试当成该项已实测。v0.1.9临时构建/安装后原生联合模式编译、资源、缺失客户端拒绝和清理见[136](evidence/136-joined-package.json)。

实机窗口恢复，普通候选126和联合候选130各300秒退出0，分别224/217次读取、新增文本0。独立三次联合基线131为4来信候选/1自身候选/2未知、无回放。新来信验收仍待输入，发送方/历史标志保持false。所有日志仅固定计数/布尔/原因；没有真实发送、模型调用或记忆写入。

## v0.1.8 视觉与出现候选（历史记录）

现有Python执行 `python -X utf8 scripts/test.py`，完整 **168/168，32.469秒，0失败/错误/跳过**：[121](evidence/121-occurrence-visual-full-suite.txt)。此前仅视觉改动时157/157、34.406秒：[115](evidence/115-visual-full-suite.txt)。最终逻辑测试之后只更新版本和文档；没有新增运行依赖或生成ZIP。

新增视觉7项、出现候选11项。视觉实际原生编译、内存位图18种场景、屏幕内虚构窗口捕获、严格协议和CLI隔离见[114](evidence/114-visual-fullcontent-fixture-fixed.txt)。候选11/11、0.039秒见[118](evidence/118-occurrence-targeted.txt)，原严格监听33/33、2.262秒见[119](evidence/119-strict-live-regression.txt)。覆盖重复文字、旧token新内容、旧组合回放、容量与批次原子性、基线/重启及终止状态。105/107和116/117保留预期失败，112保留离屏夹具与新捕获模式不兼容的失败。

视觉独立审查7/7通过，并在临时项目构建wheel验证两个C#资源、安装资源编译和清理；候选独立审查11/11与33/33通过，补充内存边界检查通过。两者均无待修复发现，未访问真实UI，分别见[122](evidence/122-visual-review.json)、[124](evidence/124-occurrence-review.json)。v0.1.8安装包复验见[123](evidence/123-candidate-package.json)。

真实视觉3次计数5来信候选/1自身候选/1未知（113），只覆盖当前浅色150%环境；候选监听120在建立基线前因private_window_not_unique停止，尚未完成真实连发验收。完整测试不能改变该实机状态。未发送、调用真实模型或写入记忆；详细限制见 [READ_CANDIDATES.md](READ_CANDIDATES.md)。

## v0.1.7 真实监听与停止诊断（历史记录）

通过 Windows 项目入口 `scripts/windows.ps1 -Action test -Python <现有解释器>` 执行完整 **150/150，77.271秒，0失败/错误/跳过**：[102](evidence/102-live-diagnostics-full-suite.txt)。产品逻辑测试后仅更新版本和文档；`pyproject.toml` 与运行时版本为0.1.7，未安装依赖、构建新包或生成ZIP。

新增14项诊断用例，定向 **33/33，6.412秒**：[100](evidence/100-identifier-count-targeted.txt)。覆盖固定原因白名单、首次原因不覆盖、接受计数原子性、中断/原生错误/超时、布局与能力模式、严格协议和极大整数边界。先失败/修复证据：85→86、90→91、93→94、96→97、99→100，均保留于 evidence。定向命令为设置 `PYTHONPATH=src` 后 `python -m unittest discover -s tests -p test_live_read.py -v`。

独立只读审查定向 **33/33，6.559秒**，无待修复代码发现。审查指出两个独立汇总不能推断逐行交叉关系，文档已修正；详见 [审查记录](evidence/104-live-diagnostics-review.json)。

实机验收**未通过**：证据92记录第一条接受、第二条因 RuntimeId 复用停止；95/101记录全宽无子控件、共享 AutomationId 及缺少发送方/滚动能力。84和89为未定位旧格式错误，87为中断的未完成尝试，88基线失败时工具另报窗口最小化。程序测试通过不改变这些结果，详见 [LIVE_READ.md](LIVE_READ.md)。本轮未发送、调用模型或写入记忆，尚不能开始自动回复。

## v0.1.6 监听连续性修复（历史记录）

保留原 6 项新增回归，先复现 19 项、6 errors（一个测试的两个子例），合法顶部移除触发旧前缀检查拒绝：[79](evidence/79-live-overlap-red.txt)。实现后定向 **19/19，1.875 秒**：[80](evidence/80-live-overlap-targeted.txt)；完整 **136/136，30.124 秒，0 失败/错误/跳过**：[81](evidence/81-live-overlap-full-suite.txt)。

版本更新为 0.1.6 后，按项目交付约定执行 `scripts/windows.ps1 -Action test -Python <现有解释器>`，最终 **136/136，30.488 秒，0 失败/错误/跳过**：[82](evidence/82-live-overlap-final-suite.txt)。`pyproject.toml` 与运行时 `__version__` 均为 0.1.6；本轮未构建新的安装包。

独立只读审查未发现 Critical / Important / Minor 问题；审查者重跑定向 19/19、1.863 秒，并执行 6 项内存边界检查全部通过。完整回归由本任务执行，审查者仅复核其证据。审查范围与保留限制见 [83](evidence/83-live-overlap-review.json)。

使用现有 Python，无安装依赖。应用目录内定向命令：设置 `PYTHONPATH=src` 后 `python -X utf8 -m unittest discover -s tests -p test_live_read.py -v`；完整命令：`python -X utf8 scripts/test.py`。覆盖后缀衔接、两条相同正文独立输出、无追加/弱锚点/变化拒绝、旧 token 重现、4096 上限整批停止及重启重新建基线。

实机证据 [78](evidence/78-live-exchange.json)：两条相同左侧来信已观察，一条经授权的固定回复由 Computer Use 发送且用户确认收到。旧有界监听因顶部移除而停止，没有返回新增观察。本次虚构快照回归不等于修复后的真实连续监听验收；未再发送、未调用真实模型、未启用自动回复。

## v0.1.5 独立只读连接（历史记录）

最终完整回归 **130/130，32.715 秒，0 失败/错误/跳过**，见 [77](evidence/77-live-read-final-suite.txt)。新增 13 项覆盖首次基线、重复文字、重启不回放、窗口/进程/列表绑定、条目变化拒绝、空列表初始化、私有管道传递绑定、异常脱敏、原生编译/清理与双 PowerShell 入口。前一轮完整回归 130/130、33.658 秒见 [72](evidence/72-live-read-full-suite.txt)。

独立审查发现读取正文前绑定校验、空列表加载历史及临时目录异常脱敏问题；修复后又补齐编译器属性检查的权限错误脱敏。已先补失败回归再修复，全部发现经审查复验关闭。证据 [70](evidence/70-live-read-review-red.txt)、[71](evidence/71-live-read-review-fixed.txt)、[75](evidence/75-live-read-stat-red.txt)、[76](evidence/76-live-read-stat-fixed.txt)。

当时微信 4.1.15.50 的原生程序取得 8 个列表项、5 个文本项，连续 3 次绑定读取成功，初始内容没有转为新观察：[69](evidence/69-live-read-initial.json)、[73](evidence/73-live-read-bound-snapshots.json)。该阶段结束时尚未收到验证消息，后续固定收发结果见本页 v0.1.6 与证据 78。未调用模型、写入记忆或保存真实聊天到仓库。

v0.1.5 wheel 临时构建/安装后原生源码存在、编译成功、缺失客户端正确拒绝：[74](evidence/74-live-read-package.json)。完整运行和局限见 [LIVE_READ.md](LIVE_READ.md)。

## 独立 OCR 候选阶段（核心仍 v0.1.4）

完整回归 **117/117，28.766 秒，0 失败/错误/跳过**，见 [62](evidence/62-ocr-candidate-regression.txt)。新增 9 项标准库测试覆盖重复行、不确定符号、非法分数、报告脱敏/一致性、字面参数、真实子进程超时与 SDK 预过滤关闭。

独立审查提出两项问题：SDK 默认过滤会隐藏部分低分识别项；报告可能在没有过滤时同时声称原始失败、过滤后成功。先补失败回归 [60](evidence/60-ocr-candidate-review-red.txt)，修复后 9 项通过 [61](evidence/61-ocr-candidate-review-fixed.txt)，审查复验已关闭两项问题。

实际候选推理另用 `.ocr-env` 实测，依赖/三个模型哈希核验通过；5 张固定虚构图中深色与空白无需核查，浅色、大字号与真实符号仍需核查。最终 **review_required / 3**，见 [63](evidence/63-ocr-candidate-final.json)。没有真实微信消息读取或发送。候选依赖不加入核心；源码树实验不打包进应用 wheel，详见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。

## v0.1.4 本地 OCR 可行性诊断

完整回归 **108/108，27.490 秒，0 失败/错误/跳过**，见 [54](evidence/54-ocr-stage-regression.txt)。新增 11 项覆盖固定虚构位图的真实系统 OCR、空白图不通过、结果脱敏、实际超时和双 PowerShell 配置隔离。独立审查无待修复发现。

本机中文引擎可运行，但识别准确性检查为 **recognition_mismatch / 3**：深色通过，浅色中文/字母数字和大字号字母数字失败。报告保留失败结果；不能把程序测试通过改写为 OCR 准确性或微信兼容通过。[实际结果](evidence/53-ocr-local-result.txt)、[临时构建安装](evidence/55-ocr-package.json)。先失败、设计修正、范围和来源详见 [OCR_CHECK.md](OCR_CHECK.md)。本轮没有读取真实聊天或发送。

## 登录后只读检查阶段（代码仍 v0.1.3）

用户确认准备后，真实客户端文件为 4.1.15.50，路径匹配 5 个进程。主窗口在前台且未最小化；同一客户端的两个可见顶层窗口各仅 8 个基础 UIA 控件，无列表/文本控件证据，身份/监听未通过。原始脱敏证据为 [45](evidence/45-wechat-live-structure-probe.txt)、[46](evidence/46-wechat-window-metadata.json)、[47](evidence/47-wechat-owned-window-structures.json)，完整说明见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。

重新运行 `.\scripts\windows.ps1 -Action test`：**97/97，24.192 秒，0 失败/错误/跳过**，见 [48-live-probe-stage-regression.txt](evidence/48-live-probe-stage-regression.txt)。这仅确认原有代码回归通过，不能把真实 UIA 控件不足的结果改写为微信兼容通过。本轮没有产品代码改动、真实聊天读取、窗口动作、真实发送或真实模型调用。

## v0.1.3 独立开发阶段

执行 `.\scripts\windows.ps1 -Action test`：**97/97，23.931 秒，0 失败/错误/跳过**。原始输出：[43-offline-stage-full-suite.txt](evidence/43-offline-stage-full-suite.txt)。已有 84 项全部保持通过，新增 12 项回调/演练用例和 1 项双 PowerShell 入口用例。

新增验证覆盖并发生产、单线程消费、先入先出/相同文本不合并、暂停/断线/切换的订阅撤销、消费不跨代次、容量上限、关闭终态、异常脱敏、SQLite 重开去重和临时目录清理。Windows 入口在故意无效的个人配置旁运行成功，原文件不变；不会读取该配置或外部模型设置。

先失败证据：[38 缺失模块](evidence/38-callback-inbox-red.txt)、[40 消费跨订阅代次](evidence/40-callback-generation-red.txt)、[41 入口未实现](evidence/41-offline-check-entry-red.txt)。通过证据：[39 回调定向测试](evidence/39-callback-inbox-targeted.txt)、[42 一键演练](evidence/42-offline-check.txt)、[44 临时构建安装后演练](evidence/44-offline-stage-package.json)。

独立审查未发现需修复问题，另行通过消费期间暂停/关闭、临时资源已打开后异常清理检查。**本阶段未交互真实微信。** 97 项是离线/虚构窗口测试，不能替代真实身份、消息来源或 UI 兼容验收。

## v0.1.2 免费只读诊断阶段

执行 `.\scripts\windows.ps1 -Action test`：**84/84，22.594 秒，0 失败/错误/跳过**。完整原始输出：[36-wechat-probe-full-suite.txt](evidence/36-wechat-probe-full-suite.txt)。74 项已有核心回归保持通过；新增 10 项诊断测试。

| 检查 | 结果与证据 |
|---|---|
| 测试先行 | 缺少 wechat_probe 模块导致预期失败：[32](evidence/32-wechat-probe-red.txt) |
| 诊断新增 10 项 | 全通过：[33](evidence/33-wechat-probe-targeted.txt)；含属性脱敏、坏 JSON/错误/超时、禁用发送/身份标志、实际 WinForms UIA、路径限定、节点/深度上限 |
| 初次临时窗口测试 | no_window 失败：[35](evidence/35-wechat-fixture-initial-failure.txt)；原因是测试窗口隐藏任务栏，修正该测试设置后通过，产品范围未放宽 |
| 实际微信前提 | 4.1.15.13，not_running，0 进程：[34](evidence/34-wechat-native-probe.txt)；退出码 3，不能宣称已验证 UI 树 |
| 发行包核验 | `pywechat127 1.9.8` wheel/sdist SHA-256 均与 PyPI 一致；未安装或执行：[31](evidence/31-pywechat127-package-audit.json) |
| 本项目构建安装 | 0.1.2 wheel 含两个 PS1 资源；临时隔离安装后模块正确返回 client_not_found：[37](evidence/37-wechat-probe-package.json) |
| 独立审查 | 无需修复的发现；审查者另行通过 10 项测试、wheel 资源与 diff 检查 |

虚构 Windows 测试窗口不代表真实微信。登录/身份/真实监听、消息边界、去重、自身过滤、重名/窗口切换、锁屏/最小化/RDP、真实模型均未验证。没有真实发送测试。

## v0.1.1 基线历史结果

GitHub 阶段提交前复验：**74/74，18.225 秒，0 失败/错误/跳过**，见 [30-github-stage-unittest.txt](evidence/30-github-stage-unittest.txt)。此轮只补充免费路线和仓库交付约定，没有修改产品代码。

## 完整测试

实际执行修复后的自动解释器入口：

```powershell
.\scripts\windows.ps1 -Action test
```

**Ran 74 tests in 18.763s — OK。74 通过，0 失败、0 错误、0 跳过。**

原 69 项全部通过；新增 1 项 CLI UTF-8 回归、4 项 PowerShell 实际执行回归。PowerShell 用例分别在 5.1 和 7 执行，包括不存在的显式解释器、损坏虚拟环境回退、配置保留与错误码传播。

完整输出：[26-windows-final-unittest.txt](evidence/26-windows-final-unittest.txt)。

## 修订包验证

新 ZIP 已在独立临时目录解压运行完整测试：**74/74，18.760 秒，退出码 0**。见 [28-windows-archive-unittest.txt](evidence/28-windows-archive-unittest.txt)。最终封装只补入文档/证据；所有源码、脚本和测试与解压实测版本逐字节一致。ZIP CRC 与 manifest 的全部 SHA-256 再次校验。源码、脚本与文档的差异空白检查通过；原始失败日志保留工具输出中的空白。

## 失败与修复证据

| 阶段 | 结果与证据 |
|---|---|
| 原包首次 Windows 实测 | 67/69；巨大时间戳后正常中文消息退出码 4；慢 HTTP 未到达服务器。[18-windows-baseline.txt](evidence/18-windows-baseline.txt) |
| 原 PowerShell 脚本 | 找不到 py，退出码 1。[19-windows-launcher-baseline.txt](evidence/19-windows-launcher-baseline.txt) |
| 新脚本回归 RED | 3 测试，4 个子用例失败（两个 Shell）；无效解释器拒绝原本已通过。[20-windows-scripts-red.txt](evidence/20-windows-scripts-red.txt) |
| 强制 ASCII 默认编码 RED | CLI 读取线程退出后挂起，测试等待超时（1 error，非业务断言失败）。[21-windows-utf8-red.txt](evidence/21-windows-utf8-red.txt) |
| 初次修复 GREEN | 73/73，通过。[22-windows-green.txt](evidence/22-windows-green.txt) |
| 独立审查回归 RED | PowerShell 5.1 对损坏 venv 的 stderr 提前终止；1 失败。[25-windows-review-red.txt](evidence/25-windows-review-red.txt) |
| 审查修复 GREEN | 最终 74/74，通过。[26-windows-final-unittest.txt](evidence/26-windows-final-unittest.txt) |

独立审查还验证了管道写线程被阻塞时，取消/总时限能够终止工作进程并回收管道；无 Critical、无遗留 Minor。审查记录见 [REVIEW.md](REVIEW.md)。

## 其他实际验证

- 9 步临时数据模拟验收全部断言通过：[23-windows-acceptance.json](evidence/23-windows-acceptance.json)。覆盖称呼重启保留、纠正、遗忘和恢复旧内容备份后不复活。
- 不带 -Python 的脚本自动发现本机解释器，默认诊断通过：[24-windows-auto-diagnose.txt](evidence/24-windows-auto-diagnose.txt)。
- `python -X utf8 -m compileall -q src scripts tests`：退出码 0。
- `pip wheel --no-deps --no-build-isolation --no-index`：v0.1.1 wheel 离线构建成功；`pip install --no-index --no-deps --target <临时目录>` 成功，未改全局环境。
- 安装后的包诊断与本地回环 HTTP 调用各成功；模型只收到一条虚构输入：[27-windows-installed-smoke.json](evidence/27-windows-installed-smoke.json)。

真实微信和外部模型均未验证。下面保留的是 **v0.1.0 的 Linux 历史证据**，不代表修改后的 v0.1.1 重新在 Linux 跑过。

---

# v0.1.0 Linux 历史测试结果

执行日期：2026-10-01（Asia/Shanghai）。执行环境：Linux、Python 3.12.14、SQLite 3.53.1。

## 自动化测试

实际执行：

```bash
python3 scripts/test.py
```

最终输出：**Ran 69 tests in 6.990s — OK**。69 项通过，0 失败、0 错误、0 跳过。

| 测试模块 | 数量 | 覆盖内容 |
|---|---:|---|
| test_config | 6 | 默认离线、配置类型/未知字段/范围、网络显式开启、凭据不进入 repr、URL 限制 |
| test_engine | 21 | 中文多行、干运行、模拟收发、重启去重、合法相同文本、白名单/自身/群聊/历史、身份切换、顺序、上下文预算、额度、未知发送、注入和日志 |
| test_memory | 17 | 来源元数据、偏好持久化/更新、临时状态、敏感拒存、检索隔离、确认清空、遗忘、摘要、备份恢复/迁移 |
| test_models | 7 | 真正 HTTP 请求发往回环假服务：契约、鉴权/配额/服务失败、格式、重定向、超时、网络禁用与端口不可达 |
| test_review_regressions | 7 | 时间回拨、旧备份遗忘、损坏/空/不匹配数据库、畸形清单、巨大时间戳、慢速响应总时限与取消 |
| test_runtime | 11 | 真正子进程：单实例竞争、重启、JSONL、暂停/恢复/停止、异常退出、备份/恢复、诊断、启动竞态、真实慢速本地 HTTP 的停止 |

完整逐项输出：[evidence/14-final-unittest.txt](evidence/14-final-unittest.txt)。机器可读记录：[evidence/test-results.json](evidence/test-results.json)。测试中的所有人物、偏好、密钥均为虚构数据。

## 其他实际验证

| 命令/操作 | 实际结果 |
|---|---|
| `python3 -m compileall -q src scripts tests` | 退出码 0 |
| `git diff --check` | 退出码 0 |
| `python3 -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir <临时目录> .` | 构建 wechat_memory_ai-0.1.0-py3-none-any.whl 成功 |
| `python3 -m pip install --no-index --no-deps --target <隔离临时目录> <wheel>` | 退出码 0；仅安装到指定临时目录，未改全局环境 |
| 从安装后的包运行 `python3 -m wechat_memory --config <示例配置> diagnose` | 退出码 0；返回 mock / fake / dry_run=true / network_enabled=false / real_wechat_verified=false |

标准库运行路线不需要 pip；构建/安装检查仅验证项目打包配置。pip 在容器以 root 运行时发出通用提示，安装目标为独立临时目录。

## 压缩包验证

已将完整项目压缩后解压到新的目录，从该目录执行 `python3 scripts/test.py`：**69 项通过，6.911 秒，退出码 0**。解压后的 23 个源码/脚本/测试文件与交付源文件的 SHA-256 全部相同。ZIP CRC 与内含 PACKAGE_MANIFEST.json 的逐文件校验通过。原始输出见 [evidence/17-archive-unittest.txt](evidence/17-archive-unittest.txt)。最终打包仅补入此验证记录等文档，程序和测试文件保持同一字节内容。

## 失败与修复证据

每个主要模块先编写测试、运行预期失败，再补实现。01/03/05/07 的最初 RED 是缺少模块的导入错误，**不将其说成已经验证了每项业务断言**。随后完整实现并运行对应行为测试。

运行控制首轮发现启动竞争，08 保留失败输出；10 的确定性竞争测试先失败，11 修复后通过。独立审查产生 12 的行为回归失败，13 修复后全部通过；14 补验结构异常恢复与真实慢速 HTTP 取消后共 69 项通过。审查详见 [REVIEW.md](REVIEW.md)。

## 未执行的验收

- Windows 解释器、msvcrt 文件锁分支、PowerShell 脚本执行。
- 普通个人微信登录/收发、真实联系人身份、窗口切换、锁屏、最小化、RDP 断开与长期稳定运行。
- 真实模型服务、实际鉴权、订阅授权或账单费用。
- wxauto/OpenClaw 安装、集成、发布版本兼容与授权许可。

因此，这份结果只能说明当前 Linux 环境的离线核心、模拟适配器、真实本地 HTTP 测试服务和子进程控制通过；**不能说明已接通真实微信或真实模型**。
