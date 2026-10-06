# 4.1.15.50 隔离观察方案：调用条件与结果判据

2026-10-06更新。本方案把343–396的静态材料转成可审阅的观察对象、记录字段和停止条件，服务于普通个人号单测试好友、中文文字、真正任务栏最小化的目标。**这是方案与证据清单，尚未运行，也未形成可调用适配器。** 产品v0.1.22、自动回复关闭。

## 当前可做与进入观察前还缺什么

当前允许继续只读固定磁盘DLL及公开材料、开发本地离线工具和文档。本方案没有新增进程访问、注入/写进程、密钥提取、聊天数据库读取、框架安装或真实发送授权。原监听保持停止，保存的最小化状态不是当前窗口认证。

唯一静态基准为 `D:\软件\Weixin\4.1.15.50\Weixin.dll`，204099112字节，SHA256 `0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b`，imagebase `0x180000000`。下列RVA只用于核对证据，不能作为直接调用、补丁或Hook安装清单。版本/哈希改变即停止沿用本方案。

372–378已补具体looper、毫秒计时、取消语义、第二scope来源和部分停止顺序。381–382补默认两级注册/查找，并确认文字表`96b69e8+d0=3a72550`，此前`96b7a68+d0=3a65aa0`为Location。文字明确调用公共封装，但位置响应消费不能外推文字；注册重名会保留已有值，目标候选也有不同来源。仍需补实际receiver/scope、文字结果对应和最终退出链，并确定非侵入观察能力能否覆盖所需字段。若公开诊断无法提供，须另行提出**具体采集方法、字段、范围与退出方式**供授权；不能因这里列出了观察项就开始访问进程。本轮无需泛化的新权限确认。

385–386已补文字本层重试预算及直接首条消费证据。文字默认预算1，在特定整体错误下允许额外尝试一次；每轮重新构造timeout。未来观察必须把一次逻辑请求与各内部尝试分开关联，不能用一次应用调用代替单次客户端提交证明。实际传输次数、重复送达处理及完整最终结果仍缺。

389–390补所选最终结果重包、本地信号和受限上层第二次调用：整体A/B与本地state2/5是不同判据，最终共享对象可能替换成另一个本地元数据对象；实际通知订阅者仍未知。上层条件包含B102、request state10、原始type49/subtype6或130及所指byte，原始type1不满足。需要增加handler调用层和结果对象类别，不能把它与385公共尝试混成一个计数。

393–396补命令5的AddMsg类型、解析返回检查、普通type1集合追加和内部字段来源；普通文字队列消费者尚未接通。候选ID字段12不在必填mask内，+168来自协议字段6；后续descriptor+10可能继续改对象，辅助布尔也未认证方向。O6须同时保留字段存在性、变换阶段、账号来源和历史边界，不能把解析通过直接当真实新来信。

## 观察清单

| 编号与目的 | 已有静态锚点 | 将来隔离观察只需记录 | 满足条件与停止条件 |
| --- | --- | --- | --- |
| O1 确认谁执行协程 | 372/374具体looper；377闭包经第二scope提交并继承executor；381默认两级注册/查找，Text表96b69e8+d0=3a72550，Location为另一张表 | 构建哈希、会话内receiver/对象/父scope编号、descriptor类别/注册来源、receiver与executor类型/表RVA、覆盖来源、提交/调用/恢复阶段、线程编号、顺序号 | 必须认证实际receiver、注册已有值及实际scope，关联同一提交与文字入口；不能从key1忽略类型归一分支。区分协程局部scope、TLS+c8和TLS+570。表不符、闭包缺失、重复或跨会话即停止，不从默认注册宣布运行可达。 |
| O2 验证恢复及等待上下文 | 367/369：状态2恢复比较保存线程ID；join区分协程、执行器和普通线程，同执行器非协程join有错误分支 | 当前/首次线程是否一致、上下文类别、状态转移、await/join开始与退出 | 不在未知线程直接调用入口；不在同一执行器普通回调中阻塞join。线程不一致、上下文未知或未退出即停止，保留未知结果。 |
| O3 验证每次尝试的计时与重试 | 385本层预算与每轮timeout；390上层第二次调用有B102/state10/原始type49子类及标志限制；373具体looper用毫秒 | 逻辑请求/handler调用/公共尝试编号、原始类型/子类与上层标志变化、原始预算及剩余值、A/B、每次timeout与退避参数、实际executor/单位、注册/到期/取出/移除阶段、单调时间差、句柄及触发次数 | 原始type1不满足390上层判据，不能由handler名称外推。先认证实际executor再解释120000/1000；不把每次参数当总时限或相乘成全局网络次数。不添加应用重试；等待取消/异常、重复/缺失保留unknown，不改变电源或重启原监听。 |
| O4 验证对象释放和停止 | 369正常清理；374一次性取出清表后才调用，取消可查空返回；378第二scope取消/等待/析构、kernel取消/等待后网络服务停止/清理；group析构可跳过join | 各对象会话内编号、持有/释放、任务取出、回调开始/退出、取消结果、group成员等待开始/退出、auto-join分支/跳过原因、网络停止、最终looper quit/join/销毁、队列清空独立事件 | group等待、析构返回、服务停止、promise完成均不能代替全部闭包退出/撤销证据。网络接口须保留子对象调整，不能把停止方法当主对象析构。若取消后调用或析构跳过等待，保留顺序并停止新增工作，不能宣称未发送；不主动释放客户端对象或强制终止微信。 |
| O5 区分提交、解析与业务结果 | 358、363–364公共任务/parse限制；386文字首项消费；389本地state分支、整体A/B保留、最终对象替换与条件本地信号；390上层promise可带错误resolve1 | handler及原始类型、逻辑请求/handler调用/尝试/任务编号、目标来源与会话内匹配编号、解析/字段存在性、声明/实际条数、整体/逐条/本地状态、结果所属层/对象类别、通知门槛与订阅者编号；缺证据用unknown | 整体0/0与本地state5可在所查条件分支共存，不能合并为单个success。最终+28不是必然原协议响应。本地数值信号无已认证对端含义；真实订阅者与更新效果待补。字段8/目标候选不等于唯一身份，任务号不代替跨尝试或目标匹配；结果未知不重发。 |
| O6 准入真实来信 | 393命令5/AddMsg与type1集合追加；394字段12→+148、字段2/3→端点候选、字段6→+168；普通集合消费、账号/方向和历史仍未闭合 | 经认证的账号/好友别名、队列/消费者会话内编号、同步阶段、来源字段存在性/零值、来源ID对应编号、赋值前后及descriptor类别、方向依据、原始类型、首批/历史/重连边界、最小化布尔 | ID候选非必填，不能以parse_ok或对象存在准入；+168及辅助布尔不能直接当is_self。先认证普通文字链、账号和最终对象语义；首批只建基线，旧/自身/unknown不交付。重连、换号、目标或历史边界变化停止，不补当前时间/伪造ID或补积压。 |
| O7 受控好友送达判据 | 385内部尝试；389本地状态/信号；390受限上层调用和带错误promise，均不提供独立好友收到证明 | 事先批准的逻辑请求编号、handler调用/公共尝试/本地任务编号、双方对应事件、最终结果对象类别、是否重复、最小化观察、人工对端确认及时间 | 须另有明确固定文本发送授权且前置条件满足，具体方案须说明各调用层。单个中文逻辑请求，本项目不追加重发或自动AI；本地信号、整体0/0或promise1不代替对端证据。内部尝试/重复/缺失不能解释则不判通过，不能外推长期可靠性。 |

O1–O4可以围绕客户端本来发生的合法行为设计观察，不等于允许本项目主动构造请求。O5只能在解析和关联证据真实可观测时成立，不能新增人工verified开关填补。O6/O7与模型、真实记忆及自动回复仍隔离。

## 最小记录格式与有限观察顺序

设计记录字段：`build_hash / run_id / sequence / sync_phase / source_field_presence / source_id_zero / queue_token / consumer_token / transform_stage / descriptor_kind / direction_basis / logical_request_token / handler_call_token / attempt_token / task_token / retry_remaining / raw_message_type / raw_subtype / upper_flag_before_after / result_layer / result_payload_kind / subscriber_token / monotonic_elapsed / stage / object_token / parent_token / thread_token / context_kind / executor_table_rva / raw_timeout / raw_backoff / certified_unit / state_before / state_after / outcome / missing_evidence`。整体/逐条/本地状态须分别标注所属层；阶段区分注册、取出、回调开始/退出及移除返回，每次会话重新分配对象编号。不保存原始地址、昵称、账号ID、正文、完整响应、数据库内容或密钥。协议字段如不能脱敏且保留可验证关联，先停在设计阶段。静态证据中的DLL RVA是代码位置，不是活跃对象地址。

1. **离线准备（当前范围）**：保持固定输入，优先普通type1集合消费、root+20账号来源、descriptor+10最终变换及首批/历史/重连边界，再补ID有效域、目标与通知订阅者；保留各层身份对应、其他分支/异常、实际receiver/scope和退出链。标清unknown，不加载DLL。393–396及本方案交付的是这一步的进展。
2. **有界只读观察（尚未授权/未实现）**：方法和前置条件具备后，方案建议一次最多5分钟或200条元数据事件，以先到者结束；无适配器发送、模型或记忆写入。预算是拟议采集上限，不是微信超时值。必须先有真实最小化状态与单账号/单目标的可信限定，不能沿用停止文件代替。
3. **一次受控发送（尚未授权/未执行）**：仅在前述缺口满足且具体发送获批后，执行一次固定中文文本，分别记提交、解析、业务响应、对端观察。任何结果不明保留unknown并结束，不通过重试“验证成功”。
4. **退出审阅**：核对事件顺序、遗漏/重复、所有权清理和观察器退出；缺少任一条件即标本次未通过，记录具体缺口。之后才讨论来源桥接与更长时间运行。自动回复仍需既有最终明确确认。

以上是下一阶段局部验证方案，不替代项目既定路线。Web、Bot/iLink/ClawBot、企业微信、公众号和旧版偏移均不作为本方案替代方案；不恢复窗口、不重启原监听、不执行已排除原生测试。

## 本轮结论与下一项

已补发送结果/重试与入站AddMsg类型和字段赋值；普通文字入队后到消费对象的身份仍未闭合。下一项为**普通集合所有权与消费、root虚槽+20的账号来源、descriptor+10最终变换及首批/历史/重连边界**；随后认证好友、ID有效域和方向。发送实际通知订阅者、其他文字/异常分支、实际receiver/scope和最终退出继续保留。当前仍无具体可实施的只读采集方法，O1–O7未开始运行验收。

证据：[367执行与恢复](evidence/367-send-executor-resume.json)、[368计时参数](evidence/368-send-timeout-parameter.json)、[369生命周期](evidence/369-send-lifetime-boundaries.json)、[370保存状态](evidence/370-send-executor-checkpoint.json)、[371静态复核](evidence/371-send-executor-validation.json)。技术说明见[兼容性报告](SEND_COMPATIBILITY_4_1_15_50.md)。

本轮新增：[372具体赋值](evidence/372-send-looper-assignment.json)、[373时钟单位](evidence/373-send-looper-clock.json)、[374派发与取消](evidence/374-send-looper-cancel-dispatch.json)、[375保存状态](evidence/375-send-looper-checkpoint.json)、[376静态复核](evidence/376-send-looper-validation.json)。

2026-10-06新增：[377上层scope来源](evidence/377-send-scope-origin.json)、[378停止边界](evidence/378-send-scope-shutdown.json)、[379保存状态](evidence/379-send-scope-checkpoint.json)、[380静态复核](evidence/380-send-scope-validation.json)。

2026-10-06续查：[381类型注册与纠正](evidence/381-send-handler-registry.json)、[382文字请求](evidence/382-send-text-request.json)、[383保存状态](evidence/383-send-target-checkpoint.json)、[384静态复核](evidence/384-send-target-validation.json)。

2026-10-06续查：[385内部重试预算](evidence/385-send-text-retry-budget.json)、[386文字响应消费](evidence/386-send-text-response-consumer.json)、[387保存状态](evidence/387-send-text-result-checkpoint.json)、[388静态复核](evidence/388-send-text-result-validation.json)。

2026-10-06续查：[389最终结果与通知](evidence/389-send-text-final-notification.json)、[390上层再次调用与结果](evidence/390-send-upper-reentry-result.json)、[391保存状态](evidence/391-send-text-final-checkpoint.json)、[392静态复核](evidence/392-send-text-final-validation.json)。

2026-10-06入站续查：[393解析与入队](evidence/393-inbound-addmsg-dispatch.json)、[394字段来源](evidence/394-inbound-field-provenance.json)、[395保存状态](evidence/395-inbound-contract-checkpoint.json)、[396静态复核](evidence/396-inbound-contract-validation.json)。
