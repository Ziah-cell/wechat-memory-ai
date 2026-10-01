# 免费路线第一阶段：只读结构诊断

2026-10-01，v0.1.2。本阶段可验收成果为发行包核验和独立 UIA 结构探针。真实微信监听、身份验证和 dry-run 尚未验收。

## 设计与选择

用户要求先免费、正常 UI Automation、本人登录、不修改客户端内存、不提取密钥、禁止真实发送。现有核心只接受 mock 事件，SQLite 串行处理。本阶段增加独立诊断进程，不放宽核心配置，不将真实 UI 事件送入模型或记忆。

核验了 pywechat 项目内 pyweixin 的实际发行包 `pywechat127 1.9.8`。包内许可文件缺失、许可元数据与仓库文字不一致，且发行包落后于仓库源码；详见 [FREE_ROUTE.md](FREE_ROUTE.md)。选用独立实现的 Windows 自带 .NET UI Automation，不引入、安装或分发候选库代码。候选声明不能替代本机账号验证。

## 使用与输出

在应用目录执行：

```powershell
.\scripts\windows.ps1 -Action probe-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe'
```

也可用 Python 源码入口 `scripts/probe-wechat.py --client-path <完整客户端路径>`，或安装本项目后执行 `python -m wechat_memory.wechat_probe --client-path <完整客户端路径>`。此模块不读取 config.toml、.env、SQLite 或模型配置。

Python 使用独立、隐藏、无 profile 的 Windows PowerShell 5.1 子进程访问 UIA，最长 15 秒。入口支持从 PowerShell 5.1/7 调用，但 UIA 执行固定使用系统 5.1/.NET Framework。系统组件不可用时返回固定错误，不自动安装组件或修改执行策略。

只匹配指定客户端路径的 Weixin.exe/WeChat.exe 进程，从一个进程主窗口开始，不从桌面递归搜索。`window_count` 是有主窗口的匹配进程数，不是该进程的全部顶层窗口数；多个聊天子窗口不能据此证明唯一会话。最大 256 个控件、深度 16；达到边界保守标记 `limited=true`。跨进程节点或主窗口变化会拒绝本次结构结果。

UIA 只逐项请求 ProcessId、ControlType、IsOffscreen。不会请求 Name、Value、Text、AutomationId、RuntimeId、焦点/操作 pattern，不点击、不滚动、不输入、不截图。PID/窗口句柄只在子进程内部用于限定范围，不进入报告。报告字段白名单只允许固定状态、版本格式、类型编号和数量；外部异常、额外字段和 stderr 不外传。

| status | 含义与后续 |
|---|---|
| structure_observed | 读取到子控件；退出码 0，仅表示结构探针成功 |
| not_running | 指定路径客户端没有匹配进程；用户本人启动后复查 |
| no_window | 匹配进程没有主窗口；可能启动中、隐藏到托盘或无交互桌面 |
| ambiguous_window | 多个匹配进程有主窗口，不能唯一选择 |
| empty_tree | 只看到根或没有子控件，不能推定账号已登录或兼容性结论 |
| window_changed | 主窗口/进程范围变化，丢弃本次结果 |
| client_not_found / invalid_client | 路径不存在或文件名不属于支持的客户端 |
| process_unavailable / uia_unavailable | 进程属性或 UIA 访问失败；不输出外部异常 |
| probe_timeout / probe_failed | 超时或子进程失败；不重试、不恢复操作 |
| invalid_probe_output / invalid_arguments / unsupported_platform | 输出校验失败、参数无效或非 Windows |

除 structure_observed 外 CLI 返回 3。所有报告始终包含 `login_state=unverified`、`identity_verified=false`、`listener_ready=false`、`real_send_supported=false`。没有输出开关可以使它成为发送器。

## 本阶段证据与边界

- 完成先失败后实现：`evidence/32-wechat-probe-red.txt`。
- 针对性测试：`evidence/33-wechat-probe-targeted.txt`。真实 Windows UIA 调用对象是完全虚构的测试窗口，验证结构计数、进程限定、节点/深度上限、无按钮点击和无文本泄露；临时同名 exe 的不同路径不会被匹配。还实际运行超时子进程和双 PowerShell 入口。
- 初次端到端测试因测试窗口隐藏任务栏而返回 no_window，保留 `evidence/35-wechat-fixture-initial-failure.txt`。依据 [Microsoft 主窗口句柄说明](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainwindowhandle)，调整测试窗口在任务栏的可见性后通过；没有为通过测试扩大产品读取范围。
- 本机现有微信 4.1.15.13：`evidence/34-wechat-native-probe.txt` 是实际运行报告，结果 not_running、0 个进程；没有真实 UI 树证据。这是环境前提阻塞，不是“UIA 不兼容”的证明。

结构计数不证明稳定身份；Microsoft 明确 [RuntimeId 可能随时间复用](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.getruntimeid)。不要将昵称、OCR、窗口句柄或 RuntimeId 填为 peer_id/message_id。

## 登录后继续

用户本人启动现有客户端，扫码登录受控的第二个普通个人号，只打开唯一测试好友窗口，确认准备完成即可；无需在聊天提交昵称、二维码、密码或密钥。

随后先运行本探针。若有 UI 结构，继续为当前测试会话设计最小身份观察与证据确认；未取得可核验的稳定身份前不采集真实聊天正文。结构不可见时记录客户端/账号前提，不尝试修改内存、注册表、降级或付费激活。

只有身份与新消息边界有实际证据后，才实现独立只读监听。回调只进有界队列，SQLite 仍由单个处理线程访问；逐项实测历史边界、连续相同文本、重启去重、自身消息、重名与窗口切换。当前没有为了填满测试矩阵而创建虚构的真实事件 ID 或监听器。
