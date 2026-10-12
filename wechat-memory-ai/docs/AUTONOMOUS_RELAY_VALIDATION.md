> 已取消路线的历史报告（2026-10-12）。下文命令/下一步不再执行；研究源码、重复程序和构建产物已删除，旧哈希仅记录当时状态，不能用于核验当前工作副本。当前方案见 [WINDOW_OPEN_PLAN.md](WINDOW_OPEN_PLAN.md)。

# 自建独立消费、持久提交与ACK中继

2026-10-11。本阶段去掉了测试驱动对每圈读/提交/ACK的调度：自建目标工作线程持续调用已知ABI入口，独立Python中继控制只读原生bridge与虚构SQLite接收器，提交成功后通过命名管道发送ACK。最终21类各3次共63项通过，382项离线产品测试通过。产品0.1.22及自动回复状态没有改变。

[537来源](evidence/537-autonomous-relay-basis.json)、[538结果](evidence/538-autonomous-relay-results.json)、[539检查点](evidence/539-autonomous-relay-checkpoint.json)保存证据。新原生入口（历史源码路径 `experiments/autonomous_relay_fixture.c`，已删除）、独立Hook包含文件（历史源码路径 `experiments/autonomous_relay_hook.inc`，已删除）、中继（历史源码路径 `experiments/autonomous_relay.py`，已删除）、接收器（历史源码路径 `experiments/autonomous_relay_ledger.py`，已删除）、测试驱动（历史源码路径 `experiments/test_autonomous_relay.py`，已删除）另存；旧51研究、29产品、24分析、353证据和旧报告/计划保持。新Hook包含文件等于上一阶段C源码删去其独立main，旧文件未改。

## 进程边界

目标工作线程自主产生虚构输入，工作间隔位于Hook外。目标ACK服务线程执行命名管道等待和处理；原调用只尝试一次门，不等待这个线程、bridge、中继或SQLite。工作正常时仍可能因容量耗尽或门竞争而停采，本轮不提供调度、吞吐或最大停顿保证。

中继自己发起read/accept/ack。测试驱动只初始化、绑定、启动、注入故障和观测；没有逐圈驱动，也没有新增守护进程。目标映射仍一页、8槽，持久表按epoch/seq去重；中继退出时目标已有数据继续留在目标内存，满载停采并报告缺口。

管道服务通过[GetNamedPipeClientProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)取得连接PID，再核对创建时间和已绑定进程；ACK负载核对目标PID/创建时间、epoch、序号及槽代次。bridge也检查预期目标身份、只读页权限及管道服务PID。只有旧绑定进程已退出后，控制面才允许绑定新bridge；活进程替换拒绝。这是会话和连接进程绑定，**不是客户端代码认证，也不抵御受信控制器或已获准中继伪造ACK**。

服务线程采用[重叠管道IO](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-server-using-overlapped-i-o)。退出时发送取消请求并等待该OVERLAPPED完成，再释放事件、线程和管道资源；[CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)返回并不等于IO已经结束。该等待不位于Hook里。

## 发现并修复的并发读取错误

原消费者先读acked再读published。如果线程在两次读取之间被抢占，其他角色可能确认旧记录并发布下一圈；原acked配新published的差值超过8，旧函数误报layout。新增确定交错：保存acked=8，完成第二圈提交/ACK并发布第三圈，随后读published=24。保留旧判断的新增变体确实返回layout、测试失败；这不是缓冲实际超过8条。

新读取函数在读取published后复核acked。ACK改变则返回changed，中继重读；只有稳定头部组合才判容量/布局。分段测试与普通read共用这个函数，槽内容继续使用冻结的前后stamp校验。最终skip_cursor删除该复核，又产生同样layout失败。修复没有改冻结的上一阶段消费者。

## 最终验收

| 检查 | 次数 | 实际结果 |
|---|---:|---|
| 自主多圈 | 3 | 每次128条、8槽，驱动未逐圈干预；全部提交并ACK |
| 三执行辅助者退出 | 9 | 分别在提交前、提交后、ACK前结束中继/bridge/接收器；目标自主完成512次原调用，published8、acked0、缺口504；重连重放至8行 |
| bridge单独退出 | 3 | 中继报告错误并退出；目标继续原调用，恢复后排空保留记录 |
| SQLite忙锁 | 3 | 数据库被其他虚构写事务锁住时原调用继续；满载停采，解除锁后提交 |
| 迟到旧批次 | 3 | 第三圈前重放第一圈，精确去重，旧ACK不回退游标 |
| 头部游标交错 | 3 | 正常路径同一复核函数返回changed，后续第三圈可以交付 |
| ACK边界输入 | 3 | seq0、超发布游标、错误槽代次、uint64最大值均拒绝，正确ACK仍可推进 |
| 连接/目标/epoch及绑定替换 | 18 | 错误连接PID、ACK目标身份、epoch、预期PID/创建时间均拒绝；活bridge被替换也拒绝 |
| ACK与写门 | 6 | ACK线程实际持门时原调用返回且采集BUSY；测试控制面模拟占门时ACK返回busy且不推进，释放后可确认 |
| 直接/嵌套原异常 | 6 | 异常传播、深度恢复，后续正常调用可交付 |
| 复用后异常停用/门内复核 | 6 | 两类均使用gate_partial/prechecked确定交错，分别对应两个负对照；不是六种不同故障点 |

三辅助者的结束请求先后发生，记录的API返回时刻最大跨度0.2756毫秒，不是原子同时终止。目标的512次调用由已运行的工作线程完成，驱动没有在失去辅助者后补发call命令。

最终63库846行，441次成功ACK在对应流的原始日志里均有此前的接收表提交回执，27次被拒ACK未推进游标。静止最终状态合计8421次成功原返回、846次发布、7575条显式缺口。最终381个子进程全部有退出记录：342退出0，33退出1（主动结束或中继检测bridge失败），6退出11（预期目标身份拒绝）。63个目标全部合作恢复入口、删除动态函数表、释放页/映射并等待线程退出。

## 失败与负对照

全部107项运行，88符合断言、19失败。首次缺实现1项，编译尚未成功时5项缺EXE；初轮19项中3项终止夹具失败；游标测试缺命令及旧判断各1项失败；修复后的游标负对照1项，以及最终七类负对照7项，全部保留退出1，没有改成expected-failure通过。

三项终止夹具失败中，原驱动先结束并等待中继，再尝试结束bridge；根据已保存代码和日志，bridge可能已经随stdin EOF退出。随后TerminateProcess失败。修正为先连续发出三次终止请求，再逐一等待并记录退出码。旧三项共六个孙进程的退出码未保存，独立审计明确列为unknown，**不补写为正常或强制退出**；其后收尾和当前无遗留进程不能替代缺失的历史退出码。

构建前另有一次固定Zig哈希字符串抄写错误，被断言拦截、编译未开始。两次真实编译失败分别是嵌套main宏冲突、保留但未引用的旧入口触发Werror；已保存编译器输出。之后三次Zig0.14.1/O2/Wall/Wextra/Werror构建均通过，最后源码和EXE分别归档。

最终相同源码/EXE的七类对照均失败：early_ack在持久表0行时就确认seq1，原未确认槽被复用到seq9；skip_peer接受了未绑定连接；skip_target_binding接受错误目标；skip_epoch接受错误会话；skip_cursor误报稳定容量损坏；late_stop在异常窗口实际多入库1行；skip_recheck在INVALID状态下错误推进发布游标，消费者拒绝交付。early_ack尤其说明：获准进程的身份正确不能证明它的ACK逻辑正确。

独立只读immutable审计全量101库1363行；完整性、外键、连续seq/代次、虚构负载、提交早于表STOP及审计前后哈希均通过。585个累计子进程中579个有退出码，另6个为上述历史缺口；最终381个无缺口。382项离线产品测试47.692秒通过；原生最终场景时间合计152.141秒，是含工作节拍与故障插桩的运行时间，不是Hook延迟。

## 自审、恢复与下一步

自行检查IO取消/完成寿命、目标/连接身份、旧绑定句柄、ACK单调范围、门竞争、提交前后崩溃、恢复去重、冻结Hook异常边界。没有子代理、Jev或替代判断模型调用。独立审计指另一份读取原始证据的脚本，不等于第三方审查。原始中继JSONL、数据库、源码和EXE在本机忽略目录保留，提交中的清单绑定其哈希。

恢复入口为`data/autonomous-relay-20261011/HANDOFF.json`。`verify_checkpoint.py`与`audit_results.py`只读可复核；prepare_ledger/prepare_hook/freeze_previous/save_basis/write_status/save_checkpoint等一次性写入脚本不要重跑。旧data目录、报告、计划、源码及证据不可删除或覆写。

**测试控制器仍存活，而且目标主线程仍由测试stdin控制生命期；stdin关闭会触发目标收尾。** 本轮验证的是三个执行消费/提交/ACK的辅助者退出，不能称所有外部进程退出的验收已经完成。下一阶段优先在新自建变体明确目标自有寿命与控制器失联/EOF语义，再验证启动控制器退出后原调用继续、目标最终资源回收和接收侧未完成事务；不能靠第三方守护者补清理冒充修复。

共享写指令自身异常、任意对象寿命、热装卸、CFG/CET、真实微信ABI/身份和生产适配器仍未证明。旧外部硬件断点双角色退出失败保持，不扩展475为实机注入，不重跑旧方案。本轮没有微信/窗口/聊天库/密钥/真实发送/模型操作。旧监听保存stopped，自动回复关闭，id40此前暂停状态不变；启用自动回复仍需最终确认。
