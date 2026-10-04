# 免费微信接入路线

## 2026-10-04 最小化入站能力核查

v0.1.22实机确认当前UIA文本项共享AutomationId、所查方向辅助字段缺失，消息列表及到绑定窗口根的祖先均无ScrollPattern。需要真实事件来源证据，不能靠unknown计数接入回复。已重新核对wxauto免费版兼容说明及wechatferry Node文档，暂未找到已验证可替代本机4.1.15.50的免费来源；没有安装、降级、注入、提取密钥或购买Plus。具体证据、准入条件与替代路线见[INBOUND_ADMISSION](INBOUND_ADMISSION.md)。

## v0.1.18普通窗口最小化读取

在现有系统.NET/UIA提供者中新增background模式，无需多选/第三方包，方向始终unknown。259普通模式最小化3927次后因读取超时停止；不能据此声称长期监听或自动回复通过。后续先处理稳定性和身份/方向来源。

## 2026-10-03常驻与最小化补充

新增独立原生多选标签模式，无第三方微信依赖。当前已最小化窗口的持续基线读取通过，真实新来信另验；未接入模型或发送。上游监听代码提示了多选UI入口，但其运行时ID去重和非对方即自身的假设未采用；没有安装/导入/分发此前许可证据不一致的软件包。原wxauto免费文档仍只声明到4.1.8.107，不能替代本机4.1.15.50验收。详见[CONTINUOUS_LISTENER.md](CONTINUOUS_LISTENER.md)。

2026-10-01 用户已确认：先做免费版本，阶段完成后直接更新 GitHub，不再要求下载修订 ZIP。此决定取代此前“免费/付费待选择”的记录；不购买、激活或默认依赖 Plus 商业适配器。

## 当前可用阶段

微信读取部分沿用v0.1.13的系统.NET/UIA与内存PrintWindow，无第三方运行依赖。随机标记后双来信只读准入已通过，指定窗口实例的只读消息源已实现；未知/矛盾/旧组合保护保留，真实自身到达过滤已在224完成当前最大化窗口内受控验收。v0.1.16增加有限日常偏好提取与自然管理。此前8次虚构DeepSeek请求暴露的偏好猜测仍作为质量失败保留；本轮未新增真实API请求，一般质量仍待验收，微信源未接入模型或发送。最新回归范围见TEST_RESULTS.md，13项原生测试继续排除。详见 [LIVE_SOURCE.md](LIVE_SOURCE.md)、[READ_CANDIDATES.md](READ_CANDIDATES.md)与[DEEPSEEK.md](DEEPSEEK.md)。免费接入指微信连接路线；未来选用云模型时，其API费用另计。

最新增加独立 RapidOCR 候选实验：项目 `.ocr-env` 安装免费依赖，核心仍无第三方依赖。固定样例的中文/字母数字识别改善，但过滤误检会漏掉真实符号，结果 **review_required / 3**，不接入自动监听/回复。完整回归 117 项通过；来源、实际结果和局限见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。

最新 v0.1.4 增加系统自带中文 OCR 的纯虚构图片诊断 `ocr-check`，无新增运行依赖。本机引擎可用，但部分样例存在中文和字母数字误差；整体 recognition_mismatch，不接入自动监听或发送。108 项程序测试通过，详见 [OCR_CHECK.md](OCR_CHECK.md)。免费路线不等于只读付费墙，当前限制来自兼容性、识别与身份验证尚未完成。

v0.1.3 保留无第三方运行依赖的离线核心、假模型和 Windows UIA 独立结构探针，并增加有界回调队列与 offline-check 纯模拟演练。完整 97 项测试通过。用户现已确认登录/测试窗口准备完成，实际客户端版本为 4.1.15.50；两个可见窗口各只有 8 个基础控件，没有联系人/消息控件证据，详见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。真实消息适配器尚未完成，不能把结构诊断或模拟回调说成已接通个人微信。

## 实际发行包核验（2026-10-01 补充）

上游 [QuickStart](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/QuickStart.md) 指向 **pywechat127**，包内模块才叫 pyweixin。不是 PyPI 上空发行文件的同名 pywechat/pyweixin 项目。GitHub API 本次确认 HEAD 仍为 `8589baa049bb91d3a500602c167f07b2f8397a13`。

直接读取 [PyPI 1.9.8 元数据](https://pypi.org/pypi/pywechat127/1.9.8/json) 和其中列出的两个实际归档，只在内存检查，不解包安装、不运行 setup.py、不 import。原始结构化证据：[31-pywechat127-package-audit.json](evidence/31-pywechat127-package-audit.json)。

| 实际文件 | 上传日期 UTC | 已复算 SHA-256 |
|---|---|---|
| pywechat127-1.9.8-py3-none-any.whl | 2026-06-10 | fcc3879a364c33ea4858ae28b4d7602677f0633979197963499d78ff1821313e |
| pywechat127-1.9.8.tar.gz | 2026-06-10 | de7f9a8281ea3e4a5ff6c2f4c00fdcfad77e89e237e8d54eea39f0d653a4c109 |

两个文件均没有 LICENSE/COPYING/NOTICE 文件；包元数据 License 为 LGPL、分类器为 LGPLv3，[仓库 LICENSE](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/LICENSE) 却以 LGPL 2.1 开头且有项目替换文字。这里记录证据不一致，不将其推定为已核清的标准 LGPL 授权，不分发该包。

发行包声明 Python >=3.10，直接依赖包括 emoji、PyAutoGUI、pycaw、pywin32、pywin32-ctypes、pywinauto、psutil、Pillow、sounddevice、soundfile、packaging。没有为结构诊断安装这些依赖。发行包内 pyweixin/__init__.py 与固定仓库提交字节不一致，包内未包含仓库新增的 Notes2MD.py；不能用仓库当前功能声明替代发行文件的验证。[固定 PyPI 版本页](https://pypi.org/project/pywechat127/1.9.8/) 写的是微信 4.1.6.x，也不是本机 4.1.15.13 兼容证明。

发行包核验阶段选择独立实现的 Windows 原生 UIA 结构探针，具体边界见 [READ_ONLY_PROBE.md](READ_ONLY_PROBE.md)。当时结果为 not_running；后续用户确认登录后已补查真实窗口，结果见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)，仍不足以实现真实消息监听。

## 免费候选重新核验

| 候选 | 一手证据与本次判断 |
|---|---|
| wxauto4 | [安装文档](https://docs.wxauto.org/docs/install.html)只明确免费版到 4.1.8.107；本机 4.1.15.13 超出该声明。[公共仓库](https://github.com/cluic/wxauto4)显示停止更新。保留历史比较，不直接安装不匹配包。 |
| pyweixin（pywechat 项目内） | [上游 README](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/README.md)称当前维护 pyweixin，声明面向微信 4.1.6+；这不是本机实测。检查到的最新提交为 `8589baa049bb91d3a500602c167f07b2f8397a13`（2026-09-26）。 |
| pyweixin 的 UI 可访问性前提 | [上游说明](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/Weixin4.0.md)明确部分账号的 UI 树不可见，不能仅凭客户端版本保证可用。本人登录后，需要先验证可读控件，再验证稳定联系人和消息标识。 |
| pyweixin 许可证 | 仓库 LICENSE 标题 LGPL 2.1、正文有定制文字，GitHub 元数据 NOASSERTION；实际包缺少许可文件且分类器 LGPLv3。已核查但尚有不一致，不导入/分发，详见上节。 |
| wechatauto-replica | [上游 README](https://github.com/fanyuantaier/wechatauto-replica/blob/c030e8f2b101143365d76c6a5546d8634e576cb7/README.md)虽声明已验证 4.1.15.13，但读取依赖进程内密钥提取和数据库解密，UI 路径包含写入 Weixin.dll 内存。与本项目已约定的正常 UI 自动化、不提取密钥/修改客户端内存的路线不符，本阶段不采用。 |

## 下一阶段的实现顺序

1. 用户已确认受控第二个普通号与唯一测试好友窗口准备好，不重复要求登录，不自动降级客户端。
2. 用户重新登录后，当前 UIA 已可读取独立测试窗口，v0.1.5 原生只读连接已验证；当前不需要 OCR 或被拒绝过的 MSAA 路线。
3. 真实连续监听已定位RuntimeId复用，现有UIA字段不足。先取得可靠的消息来源、发送方和历史边界证据；若采用像素/头像方案，需独立实现及反例验证，不能直接使用上游启发式或把未知当作来信。只读观察不接入核心，不能跳过这些条件直接自动回复。
4. 必须取得稳定的会话身份、新消息证据与重启边界。昵称或 OCR 文本本身不足以授权发送；UIA RuntimeId 也不能未经实测当成跨重启消息 ID。
5. 一次固定文本发送已由 Computer Use 完成并获用户确认，无需重做。项目发送适配器尚未开发，后续程序发送验证须另行核验目标与授权，不重用已消耗的授权。

优先验证 pyweixin 的纯 UI 路线，也可基于 Windows 自带 UI Automation 独立实现最小只读层。若该账号没有可用 UI 树，记录阻塞；OCR 可以作为后续可行性研究，但在身份与去重未可靠解决前不接入自动发送。

Windows UI Automation 的基础访问方式见 [Microsoft 官方说明](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/obtaining-ui-automation-elements)。未安装第三方微信适配器；OCR 实验依赖仅在项目隔离目录，本次连续性修复未新增依赖或操作真实微信。此前固定收发证据见 [78](evidence/78-live-exchange.json)。
