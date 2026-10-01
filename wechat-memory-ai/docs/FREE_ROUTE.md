# 免费微信接入路线

2026-10-01 用户已确认：先做免费版本，阶段完成后直接更新 GitHub，不再要求下载修订 ZIP。此决定取代此前“免费/付费待选择”的记录；不购买、激活或默认依赖 Plus 商业适配器。

## 当前可用阶段

v0.1.1 的离线核心无第三方运行依赖，默认假模型，不发生外部模型费用。Windows 的中文输入、记忆/遗忘/恢复、运行控制和 HTTP 本地服务测试已通过。免费微信适配器尚未完成，不能把这个阶段说成已接通个人微信。

## 免费候选重新核验

| 候选 | 一手证据与本次判断 |
|---|---|
| wxauto4 | [安装文档](https://docs.wxauto.org/docs/install.html)只明确免费版到 4.1.8.107；本机 4.1.15.13 超出该声明。[公共仓库](https://github.com/cluic/wxauto4)显示停止更新。保留历史比较，不直接安装不匹配包。 |
| pyweixin（pywechat 项目内） | [上游 README](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/README.md)称当前维护 pyweixin，声明面向微信 4.1.6+；这不是本机实测。检查到的最新提交为 `8589baa049bb91d3a500602c167f07b2f8397a13`（2026-09-26）。 |
| pyweixin 的 UI 可访问性前提 | [上游说明](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/Weixin4.0.md)明确部分账号的 UI 树不可见，不能仅凭客户端版本保证可用。本人登录后，需要先验证可读控件，再验证稳定联系人和消息标识。 |
| pyweixin 许可证 | [仓库 LICENSE](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/LICENSE)以 LGPL 2.1 为标题，正文有项目定制文字；GitHub 元数据显示 NOASSERTION。尚未导入或分发其代码，不能在未核对实际发行包的情况下简单标成标准 LGPL 包。 |
| wechatauto-replica | [上游 README](https://github.com/fanyuantaier/wechatauto-replica/blob/c030e8f2b101143365d76c6a5546d8634e576cb7/README.md)虽声明已验证 4.1.15.13，但读取依赖进程内密钥提取和数据库解密，UI 路径包含写入 Weixin.dll 内存。与本项目已约定的正常 UI 自动化、不提取密钥/修改客户端内存的路线不符，本阶段不采用。 |

## 下一阶段的实现顺序

1. 用户本人启动现有微信并登录受控的第二个普通个人号；不自动降级客户端。
2. 先只读检查窗口与 UI 可访问性，不抓取全部聊天、不操作其他联系人、不发送。
3. 若正常 UI 可见，核验免费依赖的具体发行包与许可，开发独立只读适配器。读取回调进入队列，由单线程核心处理。
4. 必须取得稳定的会话身份、新消息证据与重启边界。昵称或 OCR 文本本身不足以授权发送；UIA RuntimeId 也不能未经实测当成跨重启消息 ID。
5. 只在唯一测试好友上做 dry-run；实际收件人和一次发送由用户明确确认后，再单独实现固定文本发送验收。

优先验证 pyweixin 的纯 UI 路线，也可基于 Windows 自带 UI Automation 独立实现最小只读层。若该账号没有可用 UI 树，记录阻塞；OCR 可以作为后续可行性研究，但在身份与去重未可靠解决前不接入自动发送。

Windows UI Automation 的基础访问方式见 [Microsoft 官方说明](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/obtaining-ui-automation-elements)。本次未安装候选库、启动微信、切换联系人或真实收发。
