> 2026-10-12 已取消的最小化/内部采集研究计划。不得继续执行，不再保留其研究源码；当前唯一活动方案见 [WINDOW_OPEN_PLAN.md](../../WINDOW_OPEN_PLAN.md)。

# Sustained ring implementation plan

> 使用 executing-plans 在本会话自行实施和审查。用户要求自主推进、禁止子代理、保留全部证据，覆盖技能默认审批、委派、worktree和清理步骤。

**Goal:** 自建固定8槽多圈流转，只在持久提交ACK后复用。
**Architecture:** 原生页和Hook变体、只读消费者、独立SQLite接收器、受信测试控制器。
**Tech Stack:** Windows x64 / Zig0.14.1 / C11 / Python / SQLite FULL WAL。
**Spec:** ../specs/2026-10-11-sustained-ring-design.md

## 约束与复查重点

不改冻结实现；保留失败；无真实微信操作或模型调用。复查旧槽ACK误释放、读副本与复用竞争、提交前ACK、满载覆盖及异常释放顺序。控制器ACK信任、目标退出易失性明确列为限制。

## Task 1：测试与协议边界

- [ ] 新建 docs/experiments/test_sustained_ring.py，覆盖多圈、ACK及故障；缺实现运行并归档失败。
- [ ] 新建 sustained_ring_protocol.h 和 sustained_ring_fixture.c；target命令 call/scenario/race/ack，consumer命令 read/split/finish，输出JSON。
- [ ] 新建 sustained_ring_ledger.py，接口 begin/accept/stop/snapshot；accept返回提交后ack(epoch,seq,generation)。
- [ ] 构建留档并完成正向、负对照；相同正确断言不得放宽。

## Task 2：独立审计与完成

- [ ] 只读核查原始数据库、连续序号、每次ACK对应已提交行、负对照真实错误及所有自建进程退出。
- [ ] 运行 scripts/test.py 离线产品回归；核对所有冻结哈希。
- [ ] 保存534来源、535结果、536检查点及报告，顶层状态添加最新记录。
- [ ] 自行审查、按阶段commit并push origin implementation（命令级openssl，保留证书校验），保存本机HANDOFF和可恢复校验脚本。
