# Windows 微信 4.1.15.50：磁盘静态兼容性检查

2026-10-05（北京时间），接续[发送来源审计](NON_UIA_SEND_AUDIT.md)。本轮将静态检查推进到本机安装文件：只读磁盘上的 Weixin.exe 与 4.1.15.50/Weixin.dll，记录版本、哈希、PE 节、异常处理表及公开协议字符串。不加载 DLL，不访问进程内存，不取数据库密钥，不操作窗口，不发送。

**结果：精确磁盘构建已固定，但仍未定位可供本项目调用的 .50 发送入口。旧方案的 9 个函数调用 RVA 全部落在本机已登记函数区间的内部；不能直接套用旧偏移。** 这是新增的本机静态证据，不是运行兼容、最小化收发或 ABI 验证。

## 1. 本机文件身份

[343](evidence/343-disk-client-pe-compatibility.json)记录两个文件，文件版本与产品版本都为 **4.1.15.50**，PE 均为 AMD64 / PE32+。这确认了本机磁盘上的 Windows 构建，不采用搜索结果中 macOS 同号版本作为依据。

| 文件（相对安装目录） | 字节数 | SHA256 |
| --- | ---: | --- |
| Weixin.exe | 3,128,368 | a75c86e57a8ec581985f102c04d5125ce1d3f21a4043759a610ba01f06275255 |
| 4.1.15.50/Weixin.dll | 204,099,112 | 0cf6379405432385a1c442766443450f26a7689f45e53c1b4ad2822061f3113b |

Python 标准库一次只读分析之后，PowerShell 的文件版本资源、Get-FileHash、BinaryReader 分别重新读取并比对，结果一致。DLL 异常表包含 513,387 项，EXE 为 7,298 项。核对过程及范围见 [346](evidence/346-disk-pe-crosscheck.json)。两种实现由同一执行者完成，不称独立人员复审；只认证磁盘文件，不认证进程当前已加载模块的内存状态。

## 2. 旧 RVA 在新模块中的实际位置

依据 [Microsoft PE 格式](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)与 [x64 异常处理表](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170)，按节的 RVA/磁盘偏移换算，并读取包含目标 RVA 的 RUNTIME_FUNCTION 起止区间。异常表用于展开栈，不提供函数名称，也不保证覆盖所有叶函数；以下区间不能当成语义或 ABI 证明。

| 旧来源 / 名称 | 旧 RVA | .50 中所在区间起点 | 位于区间内的字节偏移 |
| --- | --- | --- | ---: |
| navysoto GetCoroCtx | 0x42010 | 0x41fd0 | 64 |
| navysoto GetMsgSvc | 0x334780 | 0x334470 | 784 |
| navysoto GetMsgCtx | 0x6c7a80 | 0x6c7a70 | 16 |
| navysoto DoSend | 0x1788af0 | 0x1788ae0 | 16 |
| navysoto SendEntry | 0x17419e0 | 0x17419c0 | 32 |
| navysoto MsgCtor | 0x72e830 | 0x72db40 | 3,312 |
| aixed create_param2 | 0xdf40 | 0xdf10 | 48 |
| aixed send_message | 0x1677a30 | 0x16777e0 | 592 |
| aixed txt_message_ctr | 0x6b2c30 | 0x6b2c20 | 16 |

navysoto 的这些常量来自已固定的 [.11.52 偏移表](https://github.com/navysoto/wxhook/blob/fbccd52713f8cc7cd1023f852bf625af4fe38624/WeixinHookCs/src/WeixinHook.Native/WeixinOffsets.cs#L20-L35)；aixed 来自本轮补取的 [.10.27 global.h](https://github.com/aixed/WeChat-Hook/blob/e905d07ade50d2c6472e4eb3bd4f3fe19cf662c6/include/global.h#L75-L87)，哈希见 [344](evidence/344-send-compat-public-refs.json)。静态检查没有把这些地址用于函数调用或断点。

另检查了 navysoto 的 DoAddMsg：本来就是函数内 Hook 点，因此“位于区间内”不能用作新的不兼容判据；这里只记录它在 .50 对应区间偏移 15，身份仍未知。aixed 的 6 个数据地址仍可映射到 .rdata，也不代表相同 vtable/全局对象。9 个函数、1 个 Hook 点、6 个数据位置共 16 项全部保留未验证状态。

不能把表中的区间起点当作“修正后的发送地址”，也不能统一减去偏移来移植。需要逐个证明函数语义、参数、对象布局、调用约定、线程与生命周期；本轮没有完成这些证明。恰好落在可执行节或某个区间起点也不会自动通过。

## 3. .50 自身的发送相关字面量

[345](evidence/345-disk-send-literal-anchors.json)只保存已知公开协议/类型名称的位置，没有读取聊天库或运行时正文。

| 公开字面量 | .50 RVA | 观察 |
| --- | --- | --- |
| /cgi-bin/micromsg-bin/newsendmsg | 0x96d8fb0 | 1处，.rdata，后接 NUL |
| SendMsgRequestNew | 0x9590251 | 1处，.rdata，后接 NUL |
| MicroMsgRequestNew | 0x95901c1 | 1处，.rdata，后接 NUL |
| SendMsgResponseNew | 0x9590371 | 1处，.rdata，后接 NUL |

旧版本的[发送研究笔记](https://github.com/mosheng20205/WechatHook4.1.10.27/blob/713ec7d6f01d858e067a623c9bf2cda64d0d3e19/docs/SEND_MESSAGE_NOTES_4.1.10.27.md#L1-L39)区分外层请求容器与单条消息元素。本轮没有把这份 .10.27 对象字段映射到 .50。

临时扫描只覆盖两种 REX 前缀下的 RIP-relative LEA 字节形状、字面量前40字节附近，以及指向字面量的64位绝对地址形状，均未找到对应引用。它不是反汇编：不验证指令边界，不覆盖所有寻址/间接表/运行时构造，也不证明代码从不使用这些字符串。117 个具名导出中未匹配 send/msg/message/coro 名称，同样不能证明内部没有发送能力。**当前只有定位线索，没有可调用发送接口。**

## 4. 公开分支复核与下一步

[344](evidence/344-send-compat-public-refs.json)保存 aixed、navysoto 和 mosheng 的公开分支/标签索引。本轮发现的 mosheng codex/realtime-message-wxid-autoreply 分支是已审计主线的祖先：ahead 0、behind 5，不能当作新增适配。只查这些仓库索引及限定公开搜索，不宣称所有 forks、私有实现或未索引项目均不存在 .50 支持；没有下载 release 二进制。

**下一项具体工作是对上述固定哈希的 .50 DLL 做离线反汇编和调用关系分析。** 先以这些字面量、请求类型及其间接引用为线索，识别请求构造/提交位置，再追踪目标 wxid、消息元素布局及线程调度，交付带证据的候选调用图和不确定项。只有语义成立才讨论隔离适配；不能以字符串 RVA、异常表起点或旧版结构直接编造调用器。

当前环境的 PATH 未找到本轮查找的 dumpbin/objdump/llvm-objdump，捆绑 Python 未带 capstone/pefile/lief。本轮未安装新分析依赖。后续工具准备应继续服务于磁盘静态分析，不安装微信 Hook 框架、加载候选 DLL 或连接账号；如确实进入安装框架/注入/取密钥/发送阶段，仍按现有授权边界单独处理。

## 验证与范围

[346](evidence/346-disk-pe-crosscheck.json)复核两个文件的版本/哈希和10个代码位置的区间；[348](evidence/348-send-compat-static-validation.json)核对来源常量、证据结构、报告链接与提交范围。临时分析脚本在忽略的 data/send-compat-20261005，仅为本轮离线研究，不是产品命令或兼容适配器。二进制及其代码字节没有提交或上传，只有哈希、公开地址/结构元数据和结论进入证据。

[347](evidence/347-send-compat-checkpoint.json)读取保存状态仍为 stopped/native_reader_timeout，24569成功快照、24505最小化、unknown1，防待机请求不活动；最小化字段仍仅最后观察。未重启监听、恢复窗口、改电源或处理积压。产品仍 v0.1.22，真实接收尚未连 Engine，自动回复关闭；未运行产品回归、13项原生测试或第三方候选，未读 .env/密钥或让真实聊天进入模型/记忆/发送。
