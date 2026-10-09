# 4.1.15.50 隔离观察方案：调用条件与结果判据

## 最新：多线程有界观察通过108次夹具检查，微信准入仍关闭（490–494）

2026-10-09。沿用475及用户最新“授权继续”，把共享调试对象接手、新/退出线程跟踪及有界脱敏投影集成到同一实验。[完整报告](BOUNDED_RECEIVE_GUARDED_THREADS.md)、[490基线](evidence/490-bounded-receive-guarded-baselines.json)：旧单线程实现新线程命中0；新实现正常匹配248字节/8次，只输出HMAC，方向/来源仍unknown。新增状态句柄在持有者退出后自动释放本次暂停的三次夹具对照通过；第三方Native接口不代表稳定系统契约。

[491失败记录](evidence/491-bounded-receive-guarded-races.json)保留应用断点误分类、错误测试预期、并发取消遗留single-step、解冻后寄存器清零及恢复角色退出通知延迟。最终对已触发未交付异常保留自己的启用槽，等实际事件到达后清除，再脱离；每轮事件循环检查恢复角色。没有将失败改成预期失败或吞掉异常。

[492最终矩阵](evidence/492-bounded-receive-guarded-final.json)：36类各3次，共108次符合预期，93次继续运行、12次保留致命异常退出、3次主动退出；实际覆盖2次解冻后排空、4次清槽/解冻边界结束观察进程后的保留槽接管。恢复故意延迟200毫秒；当前事件处理和清理计时不代表完整停顿预算。下一项先在夹具补实际暂停区间/总量，及初始断点、API失败/双角色同时退出边界，再做真实身份、模块、最小化和随机标记绑定，不能直接接受微信PID。现有授权有效，不重复询问。

[493核查](evidence/493-bounded-receive-guarded-validation.json)绑定23批403次记录（含9次无调试器基线）及15份源码；保留29份产品、24份旧脚本和306份旧证据，原观察器/失败测试未改，未重跑产品或原完整原生回归。[494检查点](evidence/494-bounded-receive-guarded-checkpoint.json)保留0.1.22、自动回复关闭、旧监听保存停止；无微信/窗口/密钥/聊天库/发送/Jev操作，无遗留夹具。额度最低已知剩余35%，40%保存点已执行，id40不变；后续证据从495起。

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

## 最新：停止Jev参与；SyncKey更新与重置（447–450）

用户最新要求“继续，不要jev参加”：**停止 Jev 参与，由助手直接判断并继续工作；先前要求调用 Jev 的指令已被覆盖。** 下方Jev条目仅为历史记录，本轮及后续不再调用其判断，也不替换为其他外部判断模型。

2026-10-09（北京时间）继续固定DLL磁盘只读。[447](evidence/447-inbound-synckey-update.json)把2ea9360/2ef87d0绑定到micromsg.SyncKey/KeyVal：旧缓冲先解析，响应缓冲后解析，本helper确实检查两次解析结果。所选合并先保留旧列表每个key的首个value，再逐项以无符号较大值更新或插入响应项；旧列表后续同key不参与取最大。声明数量不一致只记录诊断后继续，输出数量改为合并集合大小。不同于444的外层解析返回丢失，不能把两层解析混为一谈。

普通响应为空时不修改缓存并返回0；旧缓冲为空时直接复制响应，不解析SyncKey，也返回0。合并失败-1/-3/-4产生空输出，2ea9360先将其写入owner+1a8，再交上层消费数值状态。下一请求经2ea6630读缓存/成员回退，若仍为空则构造实际长度1的零字节，再封装SKBuiltinBuffer_t。439中空/空比较仅为抽象条件，不代表这条正常请求构造会发空串；二进制零字节不等于空。

[448](evidence/448-inbound-synckey-reset.json)核所选后段：配置clicfg_xwechat_newsync_key_error_handle为false时，非零合并状态仍可保留处理器true；为true才返回false，且只对-1/-3显式清空并写回成员，-4不走该写回。只核调用的默认参数true，未读取实时配置。协议field1数值-2006直接替换响应字节并立即调用成员setter，发生在最终flush之前；不为其猜官方枚举名称。

getter4fac0与47220同取全局bb61c90的虚槽60；返回成员的380cc0/381550使用同一+400字符串及同一存储key地址。最终flush正常成功后另有成员写回，共同清理只清owner+1a8；下次可再次回退到成员。未认证活跃实例/账号一致性或持久写入成功。循环比较原请求与原响应，下一请求却可能采用合并值；循环继续不保证新状态进展，也不认证逐条消息新旧。

[449](evidence/449-inbound-buffer-checkpoint.json)保存监听仍停止，产品0.1.22、自动回复关闭，尚无可运行适配器。本轮没有调用Jev/其他判断模型，没有加载目标DLL、访问进程/聊天数据库、操作窗口、重启监听或真实收发。Codex可用窗口最低剩余74%（primary已用26%，secondary未知），40%监测id40继续；主任务未暂停。研究目录沿用本轮创建的data/inbound-buffer-20261008，文档时间按北京时间10月9日记。

[450](evidence/450-inbound-buffer-validation.json)记录同一执行者新鲜静态复核及31个纯值案例，非独立审查或运行验收；446列出的13个历史分析脚本保持。下一项绑定具体NewSync停止/取消闭包到已有服务取消链，明确排队回调寿命和可观测条件，不继续扩散存储内部。账号标识域/代次、方向、新旧边界及实际采集方式仍缺；随后才能形成最小接收实现，进行任务栏最小化接收与单好友受控发送验收，最后按既定确认开启自动回复。后续证据从451起。

## 最新：NewSync实际回调、解析返回与完成标记（442–446）

2026-10-08继续固定DLL磁盘只读。[443](evidence/443-inbound-newsync-result-producer.json)接通外层2ead5a0→2ead900→2eae7f0、内层job9584e78→2eaf5b0、future工厂9584f18→2eafdb0，以及提交wrapper9584fb8和完成回调9585048。wrapper内+a8是NewSyncRequest，+f8是NewSyncResponse；具体回调2eb0840经虚槽+20取得响应，再把响应与两个回调状态交给promise。复用355/364已核默认服务路径；未认证活跃实例、完整执行器和异步寿命。

两个回调状态A/B与协议response.field1分别保留，本回调不把协议field1替换成B。错误状态仍可正常resolve状态1，回调正常返回true；内层和外层任务均先发布结果，再置各自完成字1。完成字用于选择结果来源，不是解析成功、业务成功或历史排空标志。类型不匹配有异常路径，不能自动填0/0。

[444](evidence/444-inbound-newsync-parse-completion.json)直接绑定本NewSync封装解析器1070c40：内部694800会返回解析/必填/消耗输入的结果，但封装正常返回前强制AL=1，服务所查调用点也未检查该返回。此处不是把旧发送封装结论外推；仍未做异常网络运行复现，也不宣称上游所有校验都缺失。缺少parse_ok证据不能被完成字或非空响应对象补齐。

所选外层闭包传入重试预算0和原始超时参数120000。内层2ead900只在状态对非零、A为0或-110、剩余预算非零时等待并重试；因此该闭包默认不在这一层重试，不限制其他同步轮次或底层网络。构造的替代结果为A=-110/B=-1110和默认类型响应；完成字为0时读取经类型检查的context替代值。完整超时触发、取消/回调竞态及排空仍缺，不能把120000当作已验收的整次耗时。

[442](evidence/442-jev-result-decision.json)保留首次HTTP529失败及一次相同请求重试；成功返回jev-1.13.0，自动采用最高概率“实际响应生成”（0.73，confidence0.59），落实到443/444。失败调用无判断，不伪造用量。[446](evidence/446-inbound-result-validation.json)为同一执行者新鲜静态复核和纯值推演，非独立审查、运行验收；核验不重调API。

下一项核2ea9360/2ef87d0及-2006分支，接通响应缓冲向下一请求的更新、reset和重连边界，并补取消/回调寿命。方向、账号标识域/代次和具体采集方式仍缺。[445](evidence/445-inbound-result-checkpoint.json)保存监听仍停止；产品0.1.22、自动回复关闭，无可运行适配器。未加载DLL、操作窗口、重启监听、访问进程/聊天数据库或真实收发。额度本轮读取失败，最新值未知；上次成功读取为北京时间20:50监测的77%，不当作本轮数值，40%监测id40保留。441列出的12个历史脚本保持，新研究目录data/inbound-result-20261008，后续证据从447起。

## 最新：NewSync字段、继续循环与结束返回（437–441）

2026-10-08固定DLL磁盘只读。[438](evidence/438-inbound-newsync-fields.json)通过构造表、类型名和序列化字段号绑定NewSyncRequest/NewSyncResponse。请求field3和响应field4都指向SKBuiltinBuffer_t，循环使用其中field2字节串。该嵌套类型完整性只要求field1的presence，不要求字节串字段存在、非空或与field1数值一致。外层响应必填mask0xf也不能认证同步成功或历史边界。

[439](evidence/439-inbound-newsync-continuation.json)补所选正常循环：命令处理器返回true后，响应field3的低3个值位非零且请求/响应字节串不同，才继续；不同长度继续，相同空串停止，相同非空长度按实际长度做二进制比较。低位是字段值，不是presence。公式以对象有效稳定、插入的helper正常返回为条件，未证明完整CFG、并发别名安全或必然终止。

继续时当前输入mode改为6、首QWORD改为7，清理后重建请求；原始mode另存，循环结束后最终flush仍使用“原始mode==19”。因此后续请求mode6不等于已越过历史边界。处理器false会清成功标记并结束；普通低位耗尽或相同字节串结束则保留该标记。最终正常返回还受flush结果控制，true分支另有更新helper；正常结果分支都会reset批次管理器并清缓存字符串。循环停止、返回true、更新时间均不单独认证每条新消息或回调排空。

处理器的早期状态门允许响应field1数值0和-2006继续，不把-2006命名为未经认证的官方错误枚举，也不把该早期门当作完整成功条件。实际异步响应生产、解析失败/超时替代结果、响应字节串到下一请求状态的更新、重连/身份代次仍缺。

[437](evidence/437-jev-response-decision.json)保存一次真实Jev调用jev-1.13.0；按最大返回概率自动选“继续循环契约”（0.50，响应生产者0.49，confidence0.25），已落实到438/439。接近的概率只用于选工作方向。[441](evidence/441-inbound-response-validation.json)记录同一执行者的新鲜字节复核与纯值推演，非独立审查或运行验收；没有重调模型。

下一项补实际异步NewSync结果生产及解析/完成/失败路径，并接通响应缓冲到下一请求的更新与reset。保留逐条新旧/方向、账号标识域/代次、回调寿命及具体采集方式缺口。[440](evidence/440-inbound-response-checkpoint.json)保存监听仍停止，产品0.1.22、自动回复关闭，无可运行适配器。没有加载DLL、进程/聊天数据库访问、窗口操作、重启监听或真实收发。本轮Codex可用窗口最低剩余78%，40%监测id40继续有效；主任务未因额度规则暂停。436列出的12个历史脚本保持，新研究目录data/inbound-response-20261008，后续证据从442起。

## 最新：同步模式19的来源与批次传递（432–436）

2026-10-08固定DLL磁盘只读。[433](evidence/433-inbound-sync-mode-source.json)接通构造表9584308、启动时捕获owner的闭包9584948+10→2eabce0、2eb19d0虚槽+28→2ea2f60。输入记录+8的mode来自所选通道接收结果；2ea2cc0以同一owner+60检查“保存值为零，或64位相减后的有符号差>=7201”，条件真则覆盖为19，假则保留输入值，包括原有19。因此19不是首次登录专属标志，非19也不认证单条新来信。

时钟调用已由PE导入表绑定GetSystemTimeAsFileTime，配合本地整数换算确定为整秒墙钟。正常有效值下门槛为7201秒，不是7200秒或单调计时；时钟回拨、越界返回-1及相减回绕须保留。API的UTC/100纳秒单位依据见[微软系统时间文档](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeasfiletime)及[FILETIME文档](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-filetime)，客户端门槛来自本地字节。

owner+60构造为零，所查driver在CoDoSync返回true的正常分支更新它，返回false的正常分支不走该处更新时间；busy/pending可触发再次处理。mode19前后设置/清除owner+1c8并发信号，但后置清除未检查driver返回AL。这些状态不是每条消息、完整同步成功或回调排空证明。

[434](evidence/434-inbound-sync-mode-propagation.json)将mode==19一路接到批次准备及后续闭包捕获。true/false准备分支都存在追加120字节元素的路径，并采用不同的时间调整调用/选项；没有在此处按mode整批拒绝。该mode与428的内嵌删除/清空过滤状态是两件事，不可直接命名is_history。调整helper完整语义、后续闭包处理及真实新旧边界仍缺。

[432](evidence/432-jev-sync-decision.json)记录一次真实Jev调用，模型jev-1.13.0；自动采用最高概率项“追mode生产者”（0.80，confidence0.70），已落实到433/434。原始建议保留，输入中10/100“预留容量”的推测仅按数值参数保存，不拿模型或该推测补二进制结论。[436](evidence/436-inbound-sync-validation.json)为同一执行者新鲜静态复核和纯算术推演，非独立审查或运行验收。

下一项补外层请求/响应的具体类型、低位/字符串继续循环条件和调用方结果；保留通道mode其他来源、账号标识域/代次、方向、回调寿命与具体采集方式缺口。[435](evidence/435-inbound-sync-checkpoint.json)记录监听仍停止，产品0.1.22、自动回复关闭，无可运行适配器。未加载DLL、操作窗口、重启监听、访问进程/聊天数据库或真实收发。本轮读取Codex额度剩余80%，40%保存监测id40继续有效；没有因该规则停止主任务。431列出的13个历史脚本保持，新目录data/inbound-sync-20261008，后续证据从437起。

## 最新：批次过滤状态与控制参数（427–431）

2026-10-08继续固定DLL磁盘只读。[428](evidence/428-inbound-filter-owner-reset.json)绑定parent+1d0子管理器中的内嵌过滤状态+58；构造时阈值和active为零。rawtype51的选定控制路径可用操作15/16更新端点阈值，或用操作9的deleteMessages参数处理端点ID集合并启用过滤。2eb3780在active恰为1时按全局阈值、端点ID集合或端点阈值拒绝所选消息。所查外层正常flush的true/false路径都会清理集合并reset这份过滤状态；未认证异常、所有提前返回或重连阶段。

[429](evidence/429-inbound-clear-name-argument.json)核实clearAllMsg分支：name在rbp+190/R15，arg在另一字符串rbp+370；匹配名称后，230a20实际接收同一个name和默认值0。对稳定的clearAllMsg字节串，不论分类器跳过多长前缀，余下字符均非符号/数字或已耗尽，因此所查数字解析失败返回0。后续无符号old>=0跳过阈值和active写入，仍清除控制消息的append标志。这是有限静态参数不一致，不能写成运行复现，也不能据此断言所有过滤失效。

[427](evidence/427-jev-filter-decision.json)记录本轮一次真实Jev调用，返回jev-1.13.0；按用户要求自动选择最高概率项“核对名称/参数别名”（概率0.99，confidence0.98），已落实到429。模型的历史消息准入判断仍为未建立边界；选择概率不代替字节证据。

[431](evidence/431-inbound-filter-validation.json)记录同一执行者新鲜磁盘复核和纯值推演；[430](evidence/430-inbound-filter-checkpoint.json)保存监听仍停止。没有加载DLL、访问进程/聊天数据库、操作窗口、重启监听或真实收发。产品0.1.22、自动回复关闭，仍无可运行适配器。下一项查外层响应/同步阶段及数值mode19来源，补首批历史与重连边界；保留账号标识域/代次、回调寿命及可行采集方式缺口。不把active为零或reset当作“新消息已获准”。

用户新增要求：Pro额度剩余40%时保存进度。已创建本聊天的额度检查自动化（id40），每30分钟检查一次；创建时读到Codex周额度剩余83%。可读额度窗口中最低剩余不高于40%时，保存已核进度、未核改动与下一步，再通知；只提交/推送已验证的本任务改动。未知额度不按零处理，未要求停止主任务。检查有间隔，不保证恰好在40%触发。

426列出的13个历史脚本保持；新研究目录data/inbound-filter-20261008，历史证据不改，后续从432起。后续实质取舍继续实际调用Jev并自动采用返回的最高概率选项，不扩大已授权范围。

2026-10-09更新。本方案把343–454的静态材料转成可审阅的观察对象、记录字段和停止条件，服务于普通个人号单测试好友、中文文字、真正任务栏最小化的目标。**这是方案与证据清单，尚未运行，也未形成可调用适配器。** 产品v0.1.22、自动回复关闭。

## 当前可做与进入观察前还缺什么

当前允许继续只读固定磁盘DLL及公开材料、开发本地离线工具和文档。本方案没有新增进程访问、注入/写进程、密钥提取、聊天数据库读取、框架安装或真实发送授权。原监听保持停止，保存的最小化状态不是当前窗口认证。

唯一静态基准为 `D:\软件\Weixin\4.1.15.50\Weixin.dll`，204099112字节，SHA256 `0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b`，imagebase `0x180000000`。下列RVA只用于核对证据，不能作为直接调用、补丁或Hook安装清单。版本/哈希改变即停止沿用本方案。

372–378已补具体looper、毫秒计时、取消语义、第二scope来源和部分停止顺序。381–382补默认两级注册/查找，并确认文字表`96b69e8+d0=3a72550`，此前`96b7a68+d0=3a65aa0`为Location。文字明确调用公共封装，但位置响应消费不能外推文字；注册重名会保留已有值，目标候选也有不同来源。仍需补实际receiver/scope、文字结果对应和最终退出链，并确定非侵入观察能力能否覆盖所需字段。若公开诊断无法提供，须另行提出**具体采集方法、字段、范围与退出方式**供授权；不能因这里列出了观察项就开始访问进程。本轮无需泛化的新权限确认。

385–386已补文字本层重试预算及直接首条消费证据。文字默认预算1，在特定整体错误下允许额外尝试一次；每轮重新构造timeout。未来观察必须把一次逻辑请求与各内部尝试分开关联，不能用一次应用调用代替单次客户端提交证明。实际传输次数、重复送达处理及完整最终结果仍缺。

389–390补所选最终结果重包、本地信号和受限上层第二次调用：整体A/B与本地state2/5是不同判据，最终共享对象可能替换成另一个本地元数据对象；实际通知订阅者仍未知。上层条件包含B102、request state10、原始type49/subtype6或130及所指byte，原始type1不满足。需要增加handler调用层和结果对象类别，不能把它与385公共尝试混成一个计数。

397–401接通同一普通集合到扩展批次消费者的条件静态路径；源元素0x70（112）字节，扩展元素0x78（120）字节。额外+70有零源时间fallback及中途调整，转换后覆盖内部+150；root账号候选只追到成员虚槽+18，实际身份仍缺。选定新构造、rawtype1、首端点非newsapp的默认descriptor不写方向。O6须记录过滤/变换阶段，不能凭时间非零或批次存在准入。

402–405补后续门槛和分组通知：零ID/空handler在各自检查处继续不代表最终获准；manager+bf8内+2c0与全局bb8cc60不同。结果分组经manager+e8信号派发，区别另一+168信号；直接回调或executor包装均未绑定真实订阅者。O6必须分别关联源批次、结果组、状态门槛和回调阶段，不能把本地信号当新来信。

406–409补默认后端的数值tag分组和两层结果AND。空汇总可为1，部分返回向量可与汇总0共存，promise resolve也可携带0。必须分开子任务、组和外层结果；额外+e8派发入口的真实实例未绑定，信号不具备专属新来信语义。

410–413补缺对象跳过子任务，以及共享下层处理器的空过滤true、空map true和非空map的`(acc&1)|byte`。在0/1值域是OR，恰为1的键才选择返回项；上层仍AND。须保留跳过数量、每层归约规则和逐键状态，不能以总标志认证全部原项或事务提交。

414–417补到具体订阅注册：生产者/订阅者使用707420，默认工厂到1799070；service+e8→4a7360注册2b9dc70和2e34690，9d9ce0桥接消息向量。解除4a7570打标记，不能视为排队工作清空。活跃实例、账号和新来信判据仍未认证。

418–421补全局root捕获到task+2b8、成员赋值+68/+70、成员表8fa9498+18返回字符串+48，以及同一root的清空任务。字符串来自初始化记录首字段，所选上游为result+88；实际标识域、byte+4业务含义与生命周期仍待查。两次Jev仅辅助选择调查优先级，不提供采集认证。

2026-10-08继续固定DLL磁盘只读。[423](evidence/423-inbound-account-field-origin.json)把result+88追到`UnifyAuthResponse`的field4账号段`AcctSectResp`，再到其field1字符串。42b160在输入两个DWORD状态均为零时写内部byte+4=1；另由响应field2的值bit1控制所选账号字符串复制。该值位与协议presence位不同，byte1不能单独认证有效身份。

完整性检查有明确缺口：外层账号段可缺省，账号段必填mask0x44也不包含field1的presence mask0x1。因此检查通过不要求这个字符串存在或非空。mode1还会用已有input+60覆盖result+88，标识域、活跃账号、身份代次和借用值寿命仍未认证，不能直接命名为已认证wxid。

[424](evidence/424-inbound-auth-response-callback.json)补实际响应对象及选定mode0回调：48c440构造共享UnifyAuthResponse；secmanualauth包装器内+c8为同一协议类型，回调经虚槽+20取得并复制到结果，随后resolve和替换上层共享响应。完成标记、promise状态1及回调返回true都不要求业务成功。这里只核选定路径，未认证整个混淆控制流、所有mode1替换或实时网络解析。

[422](evidence/422-jev-origin-decision.json)是本轮一次真实Jev调用，模型`jev-1.13.0`。按用户最新要求，每次返回后自动选概率最大的选项并继续；本轮最高为响应类型绑定（概率0.56、过滤状态0.43；confidence0.34），已落实到424；身份准入的最高项为保持未准入。概率与confidence分开保留，不把选择当作证据。Jev不代替字节核查、独立审查或微信回复模型。

下一项转到2eb3780过滤状态的具体归属、启用/reset与首批历史/重连边界；保留input+60来源、标识域/身份代次和采集方式缺口，不重复已绑定的默认类型与root成员赋值。[426](evidence/426-inbound-origin-validation.json)为同一执行者新鲜磁盘复核及纯值判据推演，[425](evidence/425-inbound-origin-checkpoint.json)保存监听仍停止。产品0.1.22、自动回复关闭，无可运行适配器；最小化接收、受控发送确认和最后开启自动回复仍待完成。

只向Jev提交抽象代码事实；密钥仅用于请求头，不入证据。未操作窗口、重启监听、加载DLL、访问进程/聊天数据库或真实收发。421列出的12个历史脚本保持，新研究目录data/inbound-origin-20261008；历史证据不改，后续从427起。

## 观察清单

| 编号与目的 | 已有静态锚点 | 将来隔离观察只需记录 | 满足条件与停止条件 |
| --- | --- | --- | --- |
| O1 确认谁执行协程 | 372/374具体looper；377闭包经第二scope提交并继承executor；381默认两级注册/查找，Text表96b69e8+d0=3a72550，Location为另一张表 | 构建哈希、会话内receiver/对象/父scope编号、descriptor类别/注册来源、receiver与executor类型/表RVA、覆盖来源、提交/调用/恢复阶段、线程编号、顺序号 | 必须认证实际receiver、注册已有值及实际scope，关联同一提交与文字入口；不能从key1忽略类型归一分支。区分协程局部scope、TLS+c8和TLS+570。表不符、闭包缺失、重复或跨会话即停止，不从默认注册宣布运行可达。 |
| O2 验证恢复及等待上下文 | 367/369：状态2恢复比较保存线程ID；join区分协程、执行器和普通线程，同执行器非协程join有错误分支 | 当前/首次线程是否一致、上下文类别、状态转移、await/join开始与退出 | 不在未知线程直接调用入口；不在同一执行器普通回调中阻塞join。线程不一致、上下文未知或未退出即停止，保留未知结果。 |
| O3 验证每次尝试的计时与重试 | 385本层预算与每轮timeout；390上层第二次调用有B102/state10/原始type49子类及标志限制；373具体looper用毫秒 | 逻辑请求/handler调用/公共尝试编号、原始类型/子类与上层标志变化、原始预算及剩余值、A/B、每次timeout与退避参数、实际executor/单位、注册/到期/取出/移除阶段、单调时间差、句柄及触发次数 | 原始type1不满足390上层判据，不能由handler名称外推。先认证实际executor再解释120000/1000；不把每次参数当总时限或相乘成全局网络次数。不添加应用重试；等待取消/异常、重复/缺失保留unknown，不改变电源或重启原监听。 |
| O4 验证对象释放和停止 | 369正常清理；374一次性取出清表后才调用，取消可查空返回；378第二scope取消/等待/析构、kernel取消/等待后网络服务停止/清理；group析构可跳过join；451NewSync具体停止/互斥量；452超时job捕获 | 各对象会话内编号、持有/释放、任务取出、回调开始/退出、取消请求/promise状态/底层StopTask是否实际进入、服务使能位、任务表取出/移除与回调入口/出口、超时注册句柄移除及是否已出队、group成员等待开始/退出、auto-join分支/跳过原因、网络停止、最终looper quit/join/销毁、队列清空独立事件 | group等待、析构返回、服务停止、promise完成均不能代替全部闭包退出/撤销证据。网络接口须保留子对象调整，不能把停止方法当主对象析构。若取消后调用或析构跳过等待，保留顺序并停止新增工作，不能宣称未发送；不主动释放客户端对象或强制终止微信。 |
| O5 区分提交、解析与业务结果 | 358、363–364公共任务/parse限制；386文字首项消费；389本地state分支、整体A/B保留、最终对象替换与条件本地信号；390上层promise可带错误resolve1 | handler及原始类型、逻辑请求/handler调用/尝试/任务编号、目标来源与会话内匹配编号、解析/字段存在性、声明/实际条数、整体/逐条/本地状态、结果所属层/对象类别、通知门槛与订阅者编号；缺证据用unknown | 整体0/0与本地state5可在所查条件分支共存，不能合并为单个success。最终+28不是必然原协议响应。本地数值信号无已认证对端含义；真实订阅者与更新效果待补。字段8/目标候选不等于唯一身份，任务号不代替跨尝试或目标匹配；结果未知不重发。 |
| O6 准入真实来信 | 397–407源/扩展/内部批次、门槛、数值tag和上层AND；410缺对象跳任务；411空过滤/空map true及下层OR；419全局root成员赋值/字符串/清空；423账号field1可缺失；424选定认证回调；428内嵌过滤状态及正常批次reset；429名称/参数限制；433模式19时间/输入来源；434批次传递；438协议字段及presence；439循环与返回；443具体响应/完成字；444解析返回丢失及替代值；447SyncKey合并与零字节请求；448错误配置/成员回退/-2006写回 | 经认证账号/好友别名、账号段/首字符串presence与空值、响应值位及输入来源模式、身份字符串标识域/初始化条件、成员替换和清空阶段/会话代次、借用值的寿命依据，原项→子分组→创建任务→返回项关联，跳过原因/数量，各阶段输入/返回数量，逐键byte原值/归约规则/结果层，promise阶段，ID/时间/过滤/缓存域，控制操作与active前后值、全局/端点阈值及ID集合分支、正常reset阶段，输入/最终mode及覆盖原因、保存墙钟值存在性/差值、busy/pending和模式信号阶段，原始/逐轮mode、响应类型/来源、外层A/B与协议field1、原始parse结果/封装返回、内外完成字/替代值来源、field3值与presence分开、缓冲存在性/长度及相等关系、旧/响应/合并缓冲来源与解析状态、数值合并状态与配置实际值、owner/member缓存域、-2006立即写回与最终flush阶段、单零字节回退、循环停止原因、处理器与flush结果，最终方向依据，服务getter/实例与账号域、注册descriptor/thunk/member/executor、直接或排队回调阶段、解除标记及实际排空证据，首批历史重连和最小化布尔 | 数值tag不代替身份或rawtype，不能据同偏移合并实例；不合并下层OR与上层AND；true不证明所有原项覆盖。非零不一律等于1，缺键/类型异常单列；部分结果或空true不认证持久提交、新来信或回滚。字段+48、result+88、byte+4==1、完整性检查或完成回调均不单独认证wxid/登录成功；账号段/字符串缺失或空值保持unknown，不将response+30的值bit1当presence；成员替换或清空时停止沿用旧身份与去重域。身份/方向/活跃订阅未绑定保持unknown；零返回/空缓存/合并完成均不认证解析成功或新消息；成员回退与owner清空分开，配置未知不能取默认当实值；mode19不专属首次登录，mode6、空缓冲比较相同、循环结束、promise1、内外完成字或外层true均不认证历史排空；非19、模式信号结束、过滤关闭或批次reset均不认证新鲜消息，clearAllMsg所查分支不作有效全局阈值依据；首批只建基线，旧/自身/unknown不交付，边界变化停止，不补时间/ID/方向/积压。 |
| O7 受控好友送达判据 | 385内部尝试；389本地状态/信号；390受限上层调用和带错误promise，均不提供独立好友收到证明 | 事先批准的逻辑请求编号、handler调用/公共尝试/本地任务编号、双方对应事件、最终结果对象类别、是否重复、最小化观察、人工对端确认及时间 | 须另有明确固定文本发送授权且前置条件满足，具体方案须说明各调用层。单个中文逻辑请求，本项目不追加重发或自动AI；本地信号、整体0/0或promise1不代替对端证据。内部尝试/重复/缺失不能解释则不判通过，不能外推长期可靠性。 |

O1–O4可以围绕客户端本来发生的合法行为设计观察，不等于允许本项目主动构造请求。O5只能在解析和关联证据真实可观测时成立，不能新增人工verified开关填补。O6/O7与模型、真实记忆及自动回复仍隔离。

## 最小记录格式与有限观察顺序

设计记录字段：`build_hash / run_id / account_section_present / account_string_present / account_string_empty / auth_value_flag / identity_input_mode / identity_epoch / identity_member_stage / identity_namespace_basis / borrowed_value_lifetime_basis / sequence / skipped_subgroup_count / subgroup_skip_reason / filtered_item_count / result_map_byte / aggregation_operator / storage_commit_evidence / child_task_token / numeric_group_tag / result_aggregation_level / input_item_count / returned_item_count / partial_result_state / result_group_token / source_group_mapping / backend_result_bit / signal_kind / subscriber_registration_state / callback_stage / batch_token / original_sync_mode / per_iteration_mode / sync_response_origin / sync_callback_status_pair / sync_protocol_status / raw_parse_result / wrapper_parse_return / inner_outer_completion / fallback_value_source / sync_response_type / response_field3_value / sync_buffer_presence / sync_buffer_length / sync_buffer_equality / sync_loop_stop_reason / sync_processor_result / sync_flush_result / incoming_sync_mode / effective_sync_mode / mode_override_reason / saved_clock_present / wall_clock_delta / driver_busy_pending / filter_owner_token / control_operation / filter_active_before_after / filter_reset_stage / filter_branch / time_value_stage / time_adjustment_basis / identity_source_state / cache_epoch / sync_phase / source_field_presence / source_id_zero / queue_token / consumer_token / transform_stage / descriptor_kind / direction_basis / logical_request_token / handler_call_token / attempt_token / task_token / retry_remaining / raw_message_type / raw_subtype / upper_flag_before_after / result_layer / result_payload_kind / cancel_requested / network_stop_executed / service_enabled_bit / task_map_removed / response_extracted / timeout_handle_removed / callback_entered / callback_exited / capture_lifetime_basis / subscriber_token / monotonic_elapsed / stage / object_token / parent_token / thread_token / context_kind / executor_table_rva / raw_timeout / raw_backoff / certified_unit / state_before / state_after / outcome / missing_evidence`。整体/逐条/本地状态须分别标注所属层；阶段区分注册、取出、回调开始/退出及移除返回，每次会话重新分配对象编号。不保存原始地址、昵称、账号ID、正文、完整响应、数据库内容或密钥。协议字段如不能脱敏且保留可验证关联，先停在设计阶段。静态证据中的DLL RVA是代码位置，不是活跃对象地址。

1. **离线准备（当前范围）**：用户已停止Jev参与。451/452已补具体NewSync停止/回调互斥量/超时闭包和正常退出顺序；下一项审阅现有最小化接收代码，逐项映射所需字段与可采集来源，收敛实现缺口。保留账号/方向/历史重连代次和回调排空缺口；不再重复通用取消或扩散存储。451–454仍是静态研究，不加载目标DLL。
2. **有界只读观察（尚未授权/未实现）**：方法和前置条件具备后，方案建议一次最多5分钟或200条元数据事件，以先到者结束；无适配器发送、模型或记忆写入。预算是拟议采集上限，不是微信超时值。必须先有真实最小化状态与单账号/单目标的可信限定，不能沿用停止文件代替。
3. **一次受控发送（尚未授权/未执行）**：仅在前述缺口满足且具体发送获批后，执行一次固定中文文本，分别记提交、解析、业务响应、对端观察。任何结果不明保留unknown并结束，不通过重试“验证成功”。
4. **退出审阅**：核对事件顺序、遗漏/重复、所有权清理和观察器退出；缺少任一条件即标本次未通过，记录具体缺口。之后才讨论来源桥接与更长时间运行。自动回复仍需既有最终明确确认。

以上是下一阶段局部验证方案，不替代项目既定路线。Web、Bot/iLink/ClawBot、企业微信、公众号和旧版偏移均不作为本方案替代方案；不恢复窗口、不重启原监听、不执行已排除原生测试。

## 本轮结论与下一项

已补具体NewSync停止/超时闭包和共享回调互斥量；取消状态、任务表移除和超时句柄移除均不认证回调退出。455已完成现有代码与字段核对，未找到可直接准入来源；下一项为**具体采集器的端到端可行性方案**。O1–O7仅约束采用相关微信内部路径的方案，不作为所有独立来源的通用字段要求；由助手直接判断，不调用Jev。input+60来源、标识域/身份代次、活跃实例、实际执行器、回调排空与采集方式仍缺；O1–O7未开始运行验收。

证据：[367执行与恢复](evidence/367-send-executor-resume.json)、[368计时参数](evidence/368-send-timeout-parameter.json)、[369生命周期](evidence/369-send-lifetime-boundaries.json)、[370保存状态](evidence/370-send-executor-checkpoint.json)、[371静态复核](evidence/371-send-executor-validation.json)。技术说明见[兼容性报告](SEND_COMPATIBILITY_4_1_15_50.md)。

本轮新增：[372具体赋值](evidence/372-send-looper-assignment.json)、[373时钟单位](evidence/373-send-looper-clock.json)、[374派发与取消](evidence/374-send-looper-cancel-dispatch.json)、[375保存状态](evidence/375-send-looper-checkpoint.json)、[376静态复核](evidence/376-send-looper-validation.json)。

2026-10-06新增：[377上层scope来源](evidence/377-send-scope-origin.json)、[378停止边界](evidence/378-send-scope-shutdown.json)、[379保存状态](evidence/379-send-scope-checkpoint.json)、[380静态复核](evidence/380-send-scope-validation.json)。

2026-10-06续查：[381类型注册与纠正](evidence/381-send-handler-registry.json)、[382文字请求](evidence/382-send-text-request.json)、[383保存状态](evidence/383-send-target-checkpoint.json)、[384静态复核](evidence/384-send-target-validation.json)。

2026-10-06续查：[385内部重试预算](evidence/385-send-text-retry-budget.json)、[386文字响应消费](evidence/386-send-text-response-consumer.json)、[387保存状态](evidence/387-send-text-result-checkpoint.json)、[388静态复核](evidence/388-send-text-result-validation.json)。

2026-10-06续查：[389最终结果与通知](evidence/389-send-text-final-notification.json)、[390上层再次调用与结果](evidence/390-send-upper-reentry-result.json)、[391保存状态](evidence/391-send-text-final-checkpoint.json)、[392静态复核](evidence/392-send-text-final-validation.json)。

2026-10-06入站续查：[393解析与入队](evidence/393-inbound-addmsg-dispatch.json)、[394字段来源](evidence/394-inbound-field-provenance.json)、[395保存状态](evidence/395-inbound-contract-checkpoint.json)、[396静态复核](evidence/396-inbound-contract-validation.json)。

2026-10-06批次续查：[397队列与时间](evidence/397-inbound-batch-consumer.json)、[398端点/root/过滤](evidence/398-inbound-key-root-filter.json)、[399默认descriptor](evidence/399-inbound-default-descriptor.json)、[400保存状态](evidence/400-inbound-owner-checkpoint.json)、[401静态复核](evidence/401-inbound-owner-validation.json)。

2026-10-06通知续查：[402消费者检查](evidence/402-inbound-consumer-gates.json)、[403分组通知](evidence/403-inbound-group-notification.json)、[404保存状态](evidence/404-inbound-notification-checkpoint.json)、[405静态复核](evidence/405-inbound-notification-validation.json)。

2026-10-07后端续查：[406分组和外层结果](evidence/406-inbound-backend-groups.json)、[407组内汇总及信号边界](evidence/407-inbound-result-aggregation.json)、[408保存状态](evidence/408-inbound-backend-checkpoint.json)、[409静态复核](evidence/409-inbound-backend-validation.json)。

2026-10-07子任务续查：[410创建与跳过](evidence/410-inbound-child-dispatch.json)、[411下层OR结果](evidence/411-inbound-storage-result.json)、[412保存状态](evidence/412-inbound-storage-checkpoint.json)、[413静态复核](evidence/413-inbound-storage-validation.json)。

2026-10-07接收入口续查：[414注册](evidence/414-inbound-subscriber-registration.json)、[415派发与解除](evidence/415-inbound-subscriber-dispatch.json)、[416保存状态](evidence/416-inbound-entry-checkpoint.json)、[417静态复核](evidence/417-inbound-entry-validation.json)。

2026-10-08身份续查：[418 Jev判断](evidence/418-jev-identity-decisions.json)、[419成员与字符串来源](evidence/419-inbound-root-member-source.json)、[420保存状态](evidence/420-inbound-identity-checkpoint.json)、[421静态复核](evidence/421-inbound-identity-validation.json)。
