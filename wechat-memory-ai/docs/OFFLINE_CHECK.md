# 无需微信登录的独立开发阶段

2026-10-01，v0.1.3。用户决定先完成独立开发，第二个普通个人微信号的登录放到后续。本阶段不启动或探测真实微信。

## 一键离线演练

```powershell
.\scripts\windows.ps1 -Action offline-check
```

源码入口也可用 `python scripts/offline-check.py`，安装本项目后可用 `python -m wechat_memory.offline_check`。不需要配置文件、账号、联系人或模型密钥；即使已有 config.toml 无效或指向网络模型，该命令也不会读取它或 .env。

程序内置虚构 mock 身份/消息，工作线程模拟回调，创建队列的线程调用原有 Engine、FakeModel 与 SQLite。临时目录中保存本次虚构数据，结束后清理；不使用用户正式数据目录。结果只输出固定检查名称和布尔值，不输出消息正文、昵称、数据库路径或外部异常。

检查包括：回调只排队不处理、相同正文不同消息 ID 分别处理、重复事件被过滤、自身/历史/其他联系人过滤、重新打开 SQLite 后的去重、没有发送、旧回调失效、会话变化丢弃积压、溢出停止、关闭后拒绝回调。成功退出 0，失败退出 1。`source=synthetic_callbacks`、`network_enabled=false`、`real_wechat_verified=false`、`real_send_supported=false` 始终明确标注。

## 回调队列的契约

`CallbackInbox` 是独立传输组件，不是微信监听器。它不访问 UI、SQLite 或模型，也不获取联系人/消息身份。

- 构造线程独占 `begin()` 和 `consume()`，确保消费端可使用默认单线程 SQLite 连接。
- `begin()` 返回绑定本次订阅的回调；不同工作线程可调用回调，短锁只保护内存队列，不等待模型、数据库或队列空位。
- 默认上限 128，最多可设 1024；事件文本最大 10000 字符，其他字符串最大 256，限定基本字段类型。业务上的身份/历史/消息类型等仍交由核心检查。
- `consume()` 每次最多取指定数量的事件；不在队列锁内执行消费函数。一次 consume 不跨越订阅代次，重新 begin 后的事件留给下一次消费。
- `suspend('paused'|'window_changed'|'disconnected')` 使旧回调失效并丢弃排队事件。关闭为终态，不能重新 begin。溢出也清空队列并停止接受，必须显式重新订阅；不静默丢一条后继续。
- 消费函数失败会清空剩余队列、失效旧回调并只抛固定 `consumer_failed`，不自动重试已交出的事件。
- **已经出队、交给消费函数的事件不能撤回。** 窗口/连接变化需要未来实际适配器检测并调用 suspend，同时消费端仍必须在处理和发送边界验证真实身份/取消状态。当前 Engine 的模拟身份检查不能作为实机证明。

订阅代次只用于本进程撤销回调，不是联系人 ID、消息 ID 或跨重启去重键。队列本身不去重，相同正文不会合并。演练中的重启去重使用核心已有的 mock 事件 ID 和 guard SQLite；真实消息 ID 的来源/稳定性仍需后续实机验证。

## 测试证据

- `evidence/38-callback-inbox-red.txt`：实现前缺失模块的预期失败。
- `evidence/40-callback-generation-red.txt`：补充测试证明一次 consume 原先会跨代次，修复为绑定调用开始时的订阅。
- `evidence/41-offline-check-entry-red.txt`：入口实现前 PowerShell 拒绝 offline-check 的预期失败。
- `evidence/39-callback-inbox-targeted.txt`：并发生产、线程限定、撤销、溢出、关闭、错误脱敏、实际 SQLite 去重与临时目录清理。
- `evidence/42-offline-check.txt`：实际一键演练报告，所有检查通过。
- `evidence/43-offline-stage-full-suite.txt`：本阶段完整回归。

原有模拟聊天入口和配置限制保持不变。真实微信监听、稳定联系人识别、历史/新消息判定、自身方向、重名/切窗/锁屏/RDP 仍待以后本人登录后验证。后续应根据实际 UI 证据实现来源层，再接入此队列；不能把 mock ID 替换成昵称或 RuntimeId 就宣称接通。
