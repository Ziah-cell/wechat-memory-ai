# 虚构持久接收表与停止确认 Implementation Plan

> For agentic workers: use superpowers:executing-plans inline. Existing authorization keeps implementation in this workspace and permits commit/push; do not use advisory models or create worktrees.

**Goal:** 消费者重启后不重复写入虚构接收表；停止确认之后不得再为该会话插入记录。

**Architecture:** 新增外部Python/SQLite接收端，复用上一阶段只读原生消费者。会话、序号、记录与操作顺序在同一数据库事务提交；停止事务与接收事务竞争同一写锁。发布回调不接触该数据库。

**Tech Stack:** Windows自建进程、原有Zig编译夹具、Python标准库sqlite3、WAL与synchronous=FULL。

**Spec:** [上一阶段交付缺口](../../RESIDENT_PUBLISHER_LIFECYCLE.md)。本页补充限定：交付指新实验SQLite中的持久接收行，不包含微信、模型、产品Store或外部网络副作用。

## Global Constraints

- 原33研究、29产品、24旧分析、332旧证据保持哈希不变；新证据从516开始。
- 新数据库只能位于本阶段忽略目录，内容只允许固定虚构记录格式。
- 真实自动回复关闭；既有475授权不扩展为注入、入口改写或发送。
- 进程强制结束测试不等于断电/磁盘损坏测试。已提交行不撤回，停止只禁止后续插入。

## Review Focus

- 提交成功但ACK丢失：重启重试不得重复插入。
- 提交前死亡：记录与游标不得只持久化一半。
- 接收事务持锁时请求停止：忙碌必须显式失败，不能虚假确认。
- 已关闭旧会话、切换新代次后迟到旧批次：必须拒绝，不得重开旧会话。
- 序号缺口、重复键内容冲突、畸形批次：整批回滚，不能推进游标。

## Task 1: 持久接收与故障对照

**Files:** 新增 `docs/experiments/resident_delivery_ledger.py` 和 `docs/experiments/test_resident_delivery.py`。

**Interfaces:** `Ledger.begin(epoch)`、`accept(epoch, records, checkpoint=None)`、`stop(epoch, checkpoint=None)`、`snapshot()`；CLI接收JSON行，成功只在COMMIT后输出ACK。测试检查点只存在于自建外部接收进程，可停在提交前/后供控制器强制结束。

- [x] 先保存缺少接收实现的失败，随后实现同事务去重与游标更新。
- [x] 用真实原生消费者重连的重复1–3条验证只产生3行，并验证新4条能继续。
- [x] 验证接收/停止的提交前后崩溃、ACK丢失重试、并发锁竞争与源目标继续运行。
- [x] 验证关闭不可重开、代次切换、序号缺口/冲突整批回滚、数据库重开状态保持。
- [x] 故障版本仅省略停止检查，原断言失败；保存而不改成成功。

## Task 2: 保存及后续

- [x] 自查交易边界、限定“接收表恰好插入一次”的含义；105个最终批次进程已退出，51个归档库只读审计通过；原文件哈希由检查点核验。
- [ ] 保存516起证据、研究报告和HANDOFF；既有额度监控已暂停，不修改。
- [ ] 提交推送并核对远端。下一项自建已知ABI函数跳板执行是独立研究，不以接收表测试代替。

## Rulings

- Ruling: 接收行与去重键用同一SQLite事务 — 单独保存“已发送”游标无法消除外部副作用与游标之间的崩溃窗口 — 因此结论仅限本地接收表，不能宣称真实发送恰好一次。
- Ruling: STOP ACK指停止事务已提交 — 同时持锁的接收可以先完成，但停止确认后无新增行 — 无法追溯撤回已经提交的行。

## 执行记录

Task 1 complete：最终17类各3次共51次符合断言；缺少实现、非对象JSON异常和故障版本各1次失败保留。非对象JSON修复后明确拒绝。额外验证STOP ACK之后较早接收ACK仍可迟到，其行已在STOP前提交。Task 2的哈希核查、证据和提交状态以516–518及本阶段HANDOFF为准；提交前不预记推送完成。
