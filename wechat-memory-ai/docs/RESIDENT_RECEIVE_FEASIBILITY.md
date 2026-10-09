# 进程内常驻发布器：可行性研究与跳板展开对照

2026-10-09。本轮继续普通个人号、单好友、真正最小化、免费方案的研究。**找到一个能正确展开所选虚构栈的跳板编码候选，但没有实现或验证微信 Hook。** 原硬件断点的双角色退出失败保持；[OS 来源核查](OS_RECEIVE_SURFACE_AUDIT.md)也没有被重新包装成可用消息源。

## 改变资源所有权的候选

旧方案把异常交付和清槽责任留在外部调试进程。新候选让采集代码、转发跳板、展开表和有限缓冲都由目标进程持有，外部进程只消费复制好的记录。这样外部消费者消失时，无需它在目标下一次执行前清理调试寄存器。这是架构假设，尚未经过完整挂钩或辅助进程退出实验。

三种形式的比较：进程内异常处理器仍要解决新线程调试槽安装与异常分类；普通函数挂钩能覆盖以后调用该入口的新线程，但引入安装时改写代码、调用约定与异常展开问题；目标已有的注册回调最省改写，但目前没有已认证的注册/注销接口。暂把**常驻发布器加函数跳板**作为自建夹具候选，不把它选成微信实施方案。

最小设计边界如下：

1. 自建目标自行加载并初始化发布器，先完成结构分配，再以合作停调用方式安装。`DllMain` 只保留最少初始化；不在加载器锁内等线程、做 IPC 或执行采集。合作启动不证明能安全热挂到运行中的微信。[Windows DLL 初始化约束](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-best-practices)。
2. 发布器自身持有代码、转发指针、展开表和映射的有效生命周期。若选用 `GetModuleHandleEx(...PIN...)`，模块会留到进程退出，不能承诺停止后卸载。停止采集只切换为直接转发原调用，跳板和必要元数据仍留在进程内；外部退出不触发自动拆钩。[模块驻留契约](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandleexw)。
3. 回调不等待消费者、文件、网络或队列空间；只做固定上限复制。第一阶段仅用自建虚构数据，固定容量、序号和不可复用会话代次。缓冲满、竞争丢失、无效对象或期限结束时停止发布并保留明确丢失状态，随后只转发原调用。计数不能替代消息完整性；尚未实现缓冲和控制协议。
4. 目标内部回调的故障会影响目标，不能沿用“观察器故障被外部进程隔离”的说法。不吞应用异常、不自动重启目标。实际 Hook 的安装/拆除、并发新线程、ABI、异常传播和全部外部辅助者退出必须各自有证据。

下一步可先验证自建目标中的发布器与消费者生命周期，之后才考虑自建程序挂钩。实机 DLL 注入、函数改写和重启微信不在475的外部断点授权内，本轮没有实施或请求这些操作。

## 固定 Detours 源码核查

固定 Microsoft Detours `main` 为 `1dbd4ea281d73d478aa8d09a8b83fbd265f715f7`，归档6份公开源码/文档，MIT许可。只下载文本，未安装、编译、执行上游库，也未修改其源码。以下是该提交的定点结果，不是对所有 Hook 库的判定。

- x64 目标入口改写为5字节相对跳转；准备跳板时复制足够的完整指令，再生成跳回剩余入口的间接跳转。[x64生成代码](https://github.com/microsoft/Detours/blob/1dbd4ea281d73d478aa8d09a8b83fbd265f715f7/src/detours.cpp#L369)、[复制入口](https://github.com/microsoft/Detours/blob/1dbd4ea281d73d478aa8d09a8b83fbd265f715f7/src/detours.cpp#L2494)。
- `DetourUpdateThread` 只登记传入线程；官方明确未登记线程可能执行混合指令。枚举一次线程不能证明没有并发新线程。[线程协调契约](https://github.com/microsoft/Detours/wiki/DetourUpdateThread)。
- 提交先改写入口，随后处理已登记线程的上下文。在所审查代码中，读取上下文失败会跳过该线程；设置上下文、恢复页权限、刷新指令缓存及恢复线程的返回值没有全部并入最终错误值。因此不能仅凭事务返回0声称满足本项目的所有故障恢复要求。本轮未注入这些 API 故障。[提交与清理](https://github.com/microsoft/Detours/blob/1dbd4ea281d73d478aa8d09a8b83fbd265f715f7/src/detours.cpp#L1962)、[后半段](https://github.com/microsoft/Detours/blob/1dbd4ea281d73d478aa8d09a8b83fbd265f715f7/src/detours.cpp#L2134)。
- 所检查6份文件没有命中三个动态函数表注册 API 名称；这只是固定范围的搜索。本文没有运行 Detours，不能把后面的自建 API 对照写成 Detours 实机故障。

正确挂钩还需要相同函数签名及调用约定。知道入口RDX含候选对象不足以认证整个 ABI。[使用约定](https://github.com/microsoft/Detours/wiki/Using-Detours)。

## 固定入口与实际 Windows 展开对照

重新只读校验同一 .50 DLL 哈希 `0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b`。RVA `0xa773b0` 的前5字节为 `55 41 56 56 57`，依次压入 RBP、R14、RSI、RDI，共减少栈指针32字节。原函数展开头为版本1、flags=3、序言28字节、10个展开槽；不能直接照搬给地址和指令范围不同的跳板。

[实验脚本](experiments/probe_resident_unwind.py)只在自己创建的子进程里申请可读写、不可执行的内存，写入虚构指令字节、栈和寄存器上下文。它注册动态函数表，调用 `RtlLookupFunctionEntry`、`RtlVirtualUnwind`，最后删除表并释放内存。**没有执行这些指令，没有把上下文应用到线程，没有安装挂钩，也没有加载微信 DLL。** Windows 展开规则要求动态代码提供相应元数据，实际输出仍需逐个位置检查。[x64展开规则](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170)、[展开接口](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind)、[动态表注册](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtladdfunctiontable)、[删除接口](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtldeletefunctiontable)。

| 受控变体 | 观察结果 | 命令退出 |
| --- | --- | --- |
| 四次压栈元数据，尾部 `FF25` 间接跳转 | 5个位置中4个正确；偏移5的返回地址错误，栈指针少恢复32字节 | 1 |
| 相同元数据，尾部换成6个NOP | 5个位置均正确；NOP只用于因果对照，不是可运行跳板方案 | 0 |
| NOP尾部，元数据刻意漏掉RBP压栈 | 仅偏移0正确，其余4个位置少恢复8字节 | 1 |
| 不注册表，保留间接跳转 | 原生查表5次均为空；随后自写叶函数回退模型仅1个位置正确 | 1 |
| 间接跳转，序言长度从5扩大到11 | 仍4/5正确，偏移5仍错32字节；保留失败假设 | 1 |
| `mov r11, destination; 41 FF E3`，四次压栈元数据 | 偏移0/1/3/4/5/15六处均正确，首次及最终版本各一批 | 0、0 |
| 只将最后一项的跳转改为 `49 FF E3` | 两种编码均解码为 `jmp r11`；加REX.W后偏移15又错32字节，其余5处正确 | 1 |

差异支持“特定跳转编码被识别为尾声”的解释。该结论由文档与编码对照推得，没有跟踪 Windows 展开器内部实现。`RtlVirtualUnwind` 文档将带REX.W的寄存器跳转列为尾声形式。不能把“注册成功”或“指令语义相同”当成展开正确。

合计8个子进程批次、43个位置记录：38次真实 `RtlVirtualUnwind` 调用中31次恢复正确、7次不正确；另外5个是查表后的自写回退模型，1次正确、4次不正确。7次表注册均成功删除，删除后查表均为空；8个子进程均正常退出。5个驱动命令因恢复不完整退出1，记录未改成预期成功。最终候选命令为：

```text
python docs/experiments/probe_resident_unwind.py --tail register --metadata exact
```

这6处通过只覆盖本机、所选5字节压栈前缀、虚构栈以及给定元数据。没有验证指令实际执行、原函数调用/返回、浮点参数、异常处理器、嵌套展开、CFG/CET、真实 ABI、其他构建或全部辅助者退出。使用R11也需要在完整调用约定与代码实现中核验；当前不是可直接替换 Detours 的补丁。

## 本轮保存与后续

[510源码与入口](evidence/510-resident-receive-source-audit.json)、[511展开结果](evidence/511-resident-receive-unwind.json)、[512检查点](evidence/512-resident-receive-checkpoint.json)绑定上游提交、原始批次和4个实验源码版本。原30份研究源码、29份产品源码、24份旧分析脚本、326份旧证据保持；只新增一个原生研究脚本，产品仍0.1.22，自动回复关闭。

下一项是自建进程中发布器的资源所有权、有限缓冲、停止后直接转发、消费者卡死/退出及目标退出测试。这个有限问题可以独立于实机热挂钩研究推进。不得把此次展开候选6/6当作已解决旧断点双角色故障或微信接入依据，也不重新运行没有变化的旧失败方案。
