# 免费微信接入路线

2026-10-01 用户已确认：先做免费版本，阶段完成后直接更新 GitHub，不再要求下载修订 ZIP。此决定取代此前“免费/付费待选择”的记录；不购买、激活或默认依赖 Plus 商业适配器。

## 当前可用阶段

v0.1.2 保留无第三方运行依赖的离线核心，默认假模型，新增 Windows 自带 UIA 的独立只读结构诊断。完整 84 项测试通过。真实微信消息适配器尚未完成，不能把结构诊断说成已接通个人微信。

## 实际发行包核验（2026-10-01 补充）

上游 [QuickStart](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/QuickStart.md) 指向 **pywechat127**，包内模块才叫 pyweixin。不是 PyPI 上空发行文件的同名 pywechat/pyweixin 项目。GitHub API 本次确认 HEAD 仍为 `8589baa049bb91d3a500602c167f07b2f8397a13`。

直接读取 [PyPI 1.9.8 元数据](https://pypi.org/pypi/pywechat127/1.9.8/json) 和其中列出的两个实际归档，只在内存检查，不解包安装、不运行 setup.py、不 import。原始结构化证据：[31-pywechat127-package-audit.json](evidence/31-pywechat127-package-audit.json)。

| 实际文件 | 上传日期 UTC | 已复算 SHA-256 |
|---|---|---|
| pywechat127-1.9.8-py3-none-any.whl | 2026-06-10 | fcc3879a364c33ea4858ae28b4d7602677f0633979197963499d78ff1821313e |
| pywechat127-1.9.8.tar.gz | 2026-06-10 | de7f9a8281ea3e4a5ff6c2f4c00fdcfad77e89e237e8d54eea39f0d653a4c109 |

两个文件均没有 LICENSE/COPYING/NOTICE 文件；包元数据 License 为 LGPL、分类器为 LGPLv3，[仓库 LICENSE](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/LICENSE) 却以 LGPL 2.1 开头且有项目替换文字。这里记录证据不一致，不将其推定为已核清的标准 LGPL 授权，不分发该包。

发行包声明 Python >=3.10，直接依赖包括 emoji、PyAutoGUI、pycaw、pywin32、pywin32-ctypes、pywinauto、psutil、Pillow、sounddevice、soundfile、packaging。没有为结构诊断安装这些依赖。发行包内 pyweixin/__init__.py 与固定仓库提交字节不一致，包内未包含仓库新增的 Notes2MD.py；不能用仓库当前功能声明替代发行文件的验证。[固定 PyPI 版本页](https://pypi.org/project/pywechat127/1.9.8/) 写的是微信 4.1.6.x，也不是本机 4.1.15.13 兼容证明。

本阶段选择独立实现的 Windows 原生 UIA 结构探针，具体边界见 [READ_ONLY_PROBE.md](READ_ONLY_PROBE.md)。本机实际结果 not_running；用户尚需本人登录才能核验 UI 树，暂不实现真实消息监听。

## 免费候选重新核验

| 候选 | 一手证据与本次判断 |
|---|---|
| wxauto4 | [安装文档](https://docs.wxauto.org/docs/install.html)只明确免费版到 4.1.8.107；本机 4.1.15.13 超出该声明。[公共仓库](https://github.com/cluic/wxauto4)显示停止更新。保留历史比较，不直接安装不匹配包。 |
| pyweixin（pywechat 项目内） | [上游 README](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/README.md)称当前维护 pyweixin，声明面向微信 4.1.6+；这不是本机实测。检查到的最新提交为 `8589baa049bb91d3a500602c167f07b2f8397a13`（2026-09-26）。 |
| pyweixin 的 UI 可访问性前提 | [上游说明](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/Weixin4.0.md)明确部分账号的 UI 树不可见，不能仅凭客户端版本保证可用。本人登录后，需要先验证可读控件，再验证稳定联系人和消息标识。 |
| pyweixin 许可证 | 仓库 LICENSE 标题 LGPL 2.1、正文有定制文字，GitHub 元数据 NOASSERTION；实际包缺少许可文件且分类器 LGPLv3。已核查但尚有不一致，不导入/分发，详见上节。 |
| wechatauto-replica | [上游 README](https://github.com/fanyuantaier/wechatauto-replica/blob/c030e8f2b101143365d76c6a5546d8634e576cb7/README.md)虽声明已验证 4.1.15.13，但读取依赖进程内密钥提取和数据库解密，UI 路径包含写入 Weixin.dll 内存。与本项目已约定的正常 UI 自动化、不提取密钥/修改客户端内存的路线不符，本阶段不采用。 |

## 下一阶段的实现顺序

1. 用户本人启动现有微信并登录受控的第二个普通个人号；不自动降级客户端。
2. 先只读检查窗口与 UI 可访问性，不抓取全部聊天、不操作其他联系人、不发送。
3. 若正常 UI 可见，核验免费依赖的具体发行包与许可，开发独立只读适配器。读取回调进入队列，由单线程核心处理。
4. 必须取得稳定的会话身份、新消息证据与重启边界。昵称或 OCR 文本本身不足以授权发送；UIA RuntimeId 也不能未经实测当成跨重启消息 ID。
5. 只在唯一测试好友上做 dry-run；实际收件人和一次发送由用户明确确认后，再单独实现固定文本发送验收。

优先验证 pyweixin 的纯 UI 路线，也可基于 Windows 自带 UI Automation 独立实现最小只读层。若该账号没有可用 UI 树，记录阻塞；OCR 可以作为后续可行性研究，但在身份与去重未可靠解决前不接入自动发送。

Windows UI Automation 的基础访问方式见 [Microsoft 官方说明](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/obtaining-ui-automation-elements)。本次未安装候选库、启动微信、切换联系人或真实收发。
