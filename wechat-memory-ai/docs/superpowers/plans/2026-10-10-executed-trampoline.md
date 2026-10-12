> 2026-10-12 已取消的最小化/内部采集研究计划。不得继续执行，不再保留其研究源码；当前唯一活动方案见 [WINDOW_OPEN_PLAN.md](../../WINDOW_OPEN_PLAN.md)。

# 自建跳板实际执行 Implementation Plan

> Use superpowers:executing-plans inline. Existing authorization covers own-process fixtures and normal commit/push. Stay on implementation; no worktree, advisory model, real-client patch or injection.

**Goal:** 执行自建入口→中转→C Hook→跳板→原函数余部，验证所选已知ABI的参数、返回、非易失寄存器及SEH异常传播。

**Architecture:** 自己申请的代码页含固定五字节压栈前缀、整数/浮点函数、复制前缀的跳板及R11中转。注册动态函数表，页面RW写入后切为RX并刷新指令缓存。只在无调用线程时安装；停止仅禁用采集计数，转发仍有效。结束所有调用后才恢复入口、注销表、释放页。

**Tech Stack:** 已校验的Zig0.14.1 Windows x64 C/汇编、Windows动态展开表与结构化异常处理、自建Python驱动。

**Spec:** [展开候选](../../RESIDENT_RECEIVE_FEASIBILITY.md)、[资源寿命边界](../../RESIDENT_PUBLISHER_LIFECYCLE.md)、[持久接收边界](../../RESIDENT_DELIVERY_COMMIT.md)。本轮不把它们自动视为一个已集成采集器。

## Constraints and decisions

- 原35研究、29产品、24旧分析、335旧证据保持。新证据从519起。
- 自建目标的前缀固定为`55 41 56 56 57`，只是受控复制，不是通用指令重定位器。
- 两个已知签名各6参数：uint64和double；第5/6参数在栈上。两者均按位置加权，浮点输入使用可精确表示的值。
- 额外汇编调用者设定RBP/R14/RSI/RDI哨兵，检查正常返回是否保持；其自身也提供静态展开信息。
- 异常只在自己生成的函数中访问空指针，外层SEH只接收访问违例；正式Hook不吞异常。
- 已知发布器和持久接收表不在本轮集成，仅计数验证转发/被动停止。不声称真实ABI、CFG/CET、其他构建、热安装、新线程安装竞态或长期运行验收。

## Steps

- [x] 新增 `test_executed_trampoline.py`，先保存没有原生实现的失败。
- [x] 新增 `executed_trampoline_fixture.c` 与 `trampoline_register_caller.S`；保存4次构建及所有版本，4次构建均退出0。
- [x] 比较未改入口、已安装、被动停止三种状态下整数/浮点/异常行为；安装后4线程并发调用。另验采集一次再关闭的转换，最终12类各3次。
- [x] 漏掉RBP展开槽的故障版本沿用相同断言，保存实际失败，不改为通过。
- [x] 核验恢复入口、注销表、查表为空、释放页及所有自建子进程退出；旧文件哈希保持。
- [ ] 保存报告与519起证据，提交推送并核对远端。

## Rulings

- 此次生成页中的原函数和跳板都会实际执行，与510–512只读写不可执行页上的虚构上下文不同；源文件和证据另存。
- 普通异常从原函数余部发生，不能声称覆盖跳板每条指令中的异步异常；旧六点展开对照也不扩充为这种证明。
- 增加VEH只读诊断：在真实故障上下文的副本上执行一步RtlVirtualUnwind，原上下文不改，返回CONTINUE_SEARCH。缺RBP记录的基线虽被SEH接住，但副本的RSP差8字节、RBP与RIP错误；正式版本9次均恢复6项。旧驱动的弱断言结果保留。
- 浮点最初仅求和，不能识别参数互换；先把断言改为位置加权，旧函数3类均失败，再改生成函数。同一最终源码对应36项通过及1/4的故障对照，不将故障对照改成通过。
