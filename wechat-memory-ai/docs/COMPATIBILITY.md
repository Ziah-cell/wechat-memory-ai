# 兼容性与一手来源核验

查阅日期：2026-10-01（Asia/Shanghai）。以下“文档声明”与“本机实测”严格区分。v0.1.0 在 Linux 验证；v0.1.1 已在用户 Windows 电脑补验。

最新独立 RapidOCR 候选已在项目隔离环境实测，改善固定中文/数字识别，但仍存在误检和符号漏字，报告 review_required。完整 117 项程序回归通过，不能替代真实消息或身份验收；详见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。核心仍为 v0.1.4，无第三方运行依赖。

此前 v0.1.4 在同一机器用系统 Windows OCR 识别内存虚构图片，中文引擎可用，但部分文字误识别，整体 recognition_mismatch。108 项程序测试通过不等于 OCR 或微信接入通过；详见 [OCR_CHECK.md](OCR_CHECK.md)。另一个真实 MSAA 检查在执行前被自动审批拒绝，无结果。

最新实机补充：用户已确认登录及测试好友窗口准备好，现有客户端文件版本为 **4.1.15.50**。两个可见顶层窗口各仅暴露 8 个 Window/Pane/TitleBar/Button 控件，没有列表/文本控件；主窗口前台且未最小化。当前没有可用于真实消息接入的 UIA 证据，身份和监听仍未验证。详见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。本轮没有修改或升降级微信。

v0.1.3 独立开发阶段的回调队列与 offline-check 已在同一 Windows/Python 环境通过，完整 97 项测试通过，未新增依赖。该阶段登录曾延后；下方 not_running 是 v0.1.2 当时记录，不代表最新实机状态。

## v0.1.2 历史补充

当前新增独立 Windows 原生 UIA 结构探针，不是消息适配器。完整 84 项测试通过，其中真实 UIA 测试对象为虚构 WinForms 窗口。现有微信文件 4.1.15.13 的实际探针结果是 **not_running / process_count=0**；登录、真实控件树、身份和消息 ID 未验证。[实机证据](evidence/34-wechat-native-probe.txt)、[探针边界](READ_ONLY_PROBE.md)。

已通过 GitHub API 再次确认 pywechat HEAD 为 8589baa049bb91d3a500602c167f07b2f8397a13。已读取并复算 pywechat127 1.9.8 的 wheel/sdist 哈希，包内许可文件缺失，包分类器 LGPLv3 与仓库定制 LGPL 2.1 文本不同，当前没有引入该候选。具体依赖、文件哈希与来源见 [FREE_ROUTE.md](FREE_ROUTE.md)。当前实现只使用 Windows 自带 .NET UIA 和 Python 标准库。

以下候选比较和环境记录保留为 v0.1.1 基线；其中“本轮未接入”等描述不应被理解为禁止当前独立只读诊断。核心真实发送与真实适配器配置仍拒绝。

## 本机 Windows 核验补充

- 系统：Windows 11 家庭版中文版，10.0.26200，64 位。
- 解释器：Codex 已有缓存内 Python 3.12.14 / SQLite 3.53.1；没有 `py`，PATH 中 `python` 是 WindowsApps 占位入口。未安装系统 Python。
- PowerShell：5.1 与 7.6.5 均实际执行了脚本回归。
- 微信：`D:\软件\Weixin\Weixin.exe` 的文件版本与产品版本均为 **4.1.15.13**。注册表还残留 3.9.12.51 的安装记录，但该记录指向的 `WeChat.exe` 不存在，不能视为可用客户端。检查时没有 WeChat/Weixin 进程；未启动客户端或读取聊天数据。
- 重新读取 [wxauto 安装文档](https://docs.wxauto.org/docs/install.html)，免费版仍只明确到 **4.1.8.107**；[wxauto4 公共仓库](https://github.com/cluic/wxauto4) 仍显示“停止更新”。本机 4.1.15.13 超出该已声明范围，没有证据证明免费版可用，也没有实测证明所有候选均不可用。
- Plus 安装页只给出微信 4.1 大范围，不能据此认定 4.1.15.13 已适配；尚未购买、激活或安装候选包。
- 结论：离线核心可在本机运行。真实微信适配仍需先核实对应客户端版本的发行包、许可及稳定身份能力。

## 本轮技术选择

| 项目 | 本轮采用 | 实测/限制 |
|---|---|---|
| 核心 | Python 标准库 + SQLite | v0.1.0 Linux 和 v0.1.1 Windows 分别有测试记录 |
| 微信通道 | 仅 MockAdapter | 未安装或调用真实 SDK，不能真实收发 |
| Agent | 本项目轻量对话编排 | 无工具执行、文件读写指令、插件或高权限网关 |
| 模型 | 默认 FakeModel；可选 Chat Completions 客户端 | 后者仅经本地假 HTTP 服务验证；没有真实凭据或实调用 |
| 存储 | 本地明文 SQLite，内容与 guard 分离 | 已验证重启、遗忘、旧备份恢复；不承诺磁盘取证级擦除 |
| Windows 脚本 | PowerShell 调用标准库源码入口 | v0.1.1 在 PowerShell 5.1/7 实测通过 |

项目未安装 wxauto、wxauto4、wxautox Plus 或 OpenClaw。压缩包不包含这些候选项目代码/二进制，避免把未知版本和许可直接带入交付。

## wxauto 系候选

| 一手来源 | 本次观察 | 能得出的结论 |
|---|---|---|
| [wxauto 文档首页](https://docs.wxauto.org/) | 将自身说明为 Windows UI Automation 第三方库，不是腾讯官方授权产品 | 可研究正常登录后的桌面辅助路径；不证明获得平台授权 |
| [环境与安装](https://docs.wxauto.org/docs/install.html) | 当前文档表列 Windows 10/11 等、微信 4.1；免费 wxauto4 说明 Python 3.9–3.12，页面声明客户端支持到 4.1.8.107 | 这是网页声明，**不是对用户未知客户端版本的适配结论** |
| [cluic/wxauto4 仓库](https://github.com/cluic/wxauto4) | 当前可读 README 标题为“停止更新”，页面只列 README | 公开仓库与安装文档的维护信息存在差异。不能把它称作持续维护的已选依赖；需核验实际发行包来源及许可 |
| [cluic/wxauto 仓库](https://github.com/cluic/wxauto) | 仓库显示 Apache-2.0 标记；README 另有用途限制文字，版本表未给出具体值 | 本轮不推定所有新发行包都沿用同一许可，未将代码纳入本项目 |
| [第三方服务说明](https://docs.wxauto.org/legal/third-party-services.html) | 页面日期 2026-08-28，说明非官方关系、规则与界面可能改变 | 不承诺持续兼容，不提供风险控制绕过；实际账号限制风险仍存在 |
| [Plus 商业条款](https://docs.wxauto.org/legal/commercial-license.html) | 页面日期 2026-08-28，授权范围、设备/期限按购买记录，不扩大第三方权利 | 如改用 Plus，用户需自行确认当前许可与费用；本轮未购买或激活 |

维护核验的限制：本次 GitHub API 读取未成功，未取得可固定的最新发布 tag/commit；没有编造精确最新版。wxauto4 公共 README 的停止更新信息不能反向证明商业版停止，也不能证明 pip 上的包仍适配用户电脑。

普通个人号自动化可能遇到客户端变更、功能失效和账号限制，不能承诺“绝不封号”。本轮未完整取得当前腾讯端服务条款正文，下一轮实机接入前应在官方客户端/官网核对当时条款；上述第三方说明不等于腾讯许可。只考虑本人正常登录的桌面操作，不采用注入、协议破解、提取 Cookie/令牌或绕过验证。

## OpenClaw 候选

| 一手来源 | 本次观察 | 对本项目的决定 |
|---|---|---|
| [上游仓库](https://github.com/openclaw/openclaw) 与 [LICENSE](https://github.com/openclaw/openclaw/blob/main/LICENSE) | 当前仓库公开，LICENSE 为 MIT；README 提醒工具可在宿主机运行，需配隔离 | 核心不导入 OpenClaw，以免默认扩大运行时权限；未核验具体发布版 |
| [Windows 文档](https://docs.openclaw.ai/platforms/windows) | 当前说明有原生 Windows Hub、CLI，WSL2 作为 Linux 兼容运行路径 | 不沿用旧教程“只能 WSL2”等断言；当前机器未安装其中任何路径 |
| [Chat Completions HTTP 接口](https://docs.openclaw.ai/gateway/openai-http-api) | 文档说明接口默认关闭；开启后 `/v1/chat/completions` 经 Agent 运行路径，凭据可能具有 operator 权限 | 不能把此入口当成天然受限的纯文本模型代理；不暴露公网，不在本版自动启用 |
| 同一接口的会话说明 | 文档说明 `user` 可派生稳定会话，也可显式控制会话键 | 仅记录为未来适配候选。本版没有声称实现 OpenClaw 会话，当前会话与记忆由本项目管理 |

选择轻量核心的取舍：本轮可以离线完整测试，没有浏览器/系统命令工具；以后切换 Agent 需要单独写适配、核验远端权限以及远端记忆的遗忘范围。通用 HTTP 形状兼容本身不是安全或功能兼容证明。

## 模型授权、请求契约与费用

- [OpenAI 官方 Chat Completions 参考](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)：本轮依照文本 messages、Bearer 授权和 max_completion_tokens 形状实现可选客户端。不写死模型名，不推定服务商一定接受所有字段。
- [OpenAI 官方账单说明](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)：ChatGPT 与 API 分别计费。开发用 Codex/ChatGPT 授权不自动转为本系统可用的后台 API 授权。
- 未选择具体服务商、未填写实际模型、没有读取账户凭据、没有调用真实服务。本轮测试中的 Bearer 值是明确虚构的测试字符串。
- 每次请求只执行一次；本地预留费用是用户配置的估计值，无法冒充账单。超时/取消能终止本地请求工作进程，不能保证撤销服务商已接收的计算或费用。

## 实机结论

**真实普通个人微信接入：未实现，未验证。** 已核对 Windows 和客户端文件版本，完成 Windows 离线验证；账号登录、唯一联系人稳定身份、锁屏/RDP 行为、真实模型计费仍待确认。具体执行清单见 [WINDOWS_NEXT.md](WINDOWS_NEXT.md)。
