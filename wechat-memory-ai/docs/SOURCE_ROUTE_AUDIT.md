# 免费来源代码核查（2026-10-04）

结论：本轮核查的两个候选不能直接替换当前消息来源。没有发现已经满足“本机普通个人微信、免费、正常 UI、真正最小化、可靠入站”的实现。这个结论限定于所查提交和代码路径，不是对所有免费项目的断言；本轮没有新增真实接入能力，产品仍为 v0.1.22。

## 核查范围和具体发现

[326证据](evidence/326-source-route-audit.json)保存固定提交、8个文件的路径、SHA-256 和核查行号。第三方源码仅作为文本下载到被忽略的 `data/source-audit-20261004`，未安装、导入、执行或提交；没有上传任何个人数据。没有运行其测试、配置、初始化或 UI 操作，也没有再次探测真实窗口。

| 来源 | 具体代码证据 | 对本项目的影响 |
| --- | --- | --- |
| pyweixin 主源码 `8589baa0` | [发送人解析](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/src/pyweixin/WeChatAuto.py#L4309-L4330)匹配对方显示名称前缀，其他文本都归为固定的自身标签。 | 这不是可信账号或消息角色，重名/前缀重叠仍可能混淆；未匹配也不能证明自身。 |
| 同一主源码的监听 | [4367–4402](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/src/pyweixin/WeChatAuto.py#L4367-L4402)比较当前与上次可见 CheckBox 的 RuntimeId；有新增时更新当前集合，结束指定时长后批量返回。 | 内容改变但 RuntimeId 复用可能漏检，历史重现或补入可能算新增；该接口没有逐条交付回调，不能直接当低延迟消息流。 |
| 同一仓库的 MCP 副本 | [4145–4170](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/Mcp/pyweixin_rpa/pyweixin/WeChatAuto.py#L4145-L4170)仅比较最后一项 RuntimeId，与主源码不同。 | 一次轮询间有多条新增时可能只记录末条；不能拿主源码的行为替 MCP 副本背书。 |
| pyweixin 目标选择 | [1374–1461](https://github.com/Hello-Mr-Crab/pywechat/blob/8589baa049bb91d3a500602c167f07b2f8397a13/src/pyweixin/WeChatTools.py#L1374-L1461)按名称搜索，取首个匹配，再打开/选择/最小化。 | 没有给本项目补出独立的稳定目标认证；本轮不调用这些操作。 |
| FreeWisdom/wxauto-4.0 `bd7c5233` | [消息分类](https://github.com/FreeWisdom/wxauto-4.0/blob/bd7c5233e79c0a185638a325bf6d30607244dfa8/wxauto4/msgs/msg.py#L28-L54)需要消息截图，[方向函数](https://github.com/FreeWisdom/wxauto-4.0/blob/bd7c5233e79c0a185638a325bf6d30607244dfa8/wxauto4/utils/tools.py#L141-L200)在没有变化列时仍返回右侧。 | 返回 friend/self 字段不等于提供非视觉方向证据；当前不采用该兜底。没有运行任何图像/原生夹具。 |
| 同一 wxauto 分支的新增检测 | [219–301](https://github.com/FreeWisdom/wxauto-4.0/blob/bd7c5233e79c0a185638a325bf6d30607244dfa8/wxauto4/ui/chatbox.py#L219-L301)使用 RuntimeId 和数量差，数量增加时取尾部，即使 ID 重复也可交付。 | 历史从头部补入可能导致旧尾部被当作新增；数量变化不是历史边界。 |
| 同一分支的支持声明 | [README](https://github.com/FreeWisdom/wxauto-4.0/blob/bd7c5233e79c0a185638a325bf6d30607244dfa8/README.md#L511-L514)明确最小化/关闭时监听停止响应；开头仅声明 4.0.5。 | 不满足本机 4.1.15.50 的严格最小化目标。它是本次核查的一个分支，不代表官方免费版或所有其他分支。 |

pyweixin 主源码提交与此前记录相同。本轮新增的是对具体判断条件、MCP 副本差异和交付时点的审查，不宣称发现了一个新兼容版本。既有发行包与许可证据问题仍保留，未重做发行包审核。

## 可复现的离线反例

运行 `python docs/experiments/check_source_assumptions.py`。该脚本由本项目编写，只实现上述小段判断规则的投影并调用本项目纯 Python 会话；不执行第三方模块，不代表完整模拟第三方客户端。

[328](evidence/328-source-countermodels-final.json)共12检查通过：8个反例重现昵称同名/嵌套、未知被当自身、RuntimeId复用漏检、历史返回/前插、MCP末条检测漏连发，以及数量增长误交付旧尾部；4个本地守卫检查确认当前 background 仍为 unknown、复用仅算未知观察、旧组合重现和历史前插仍停止。**反例检查通过表示证明了规则的局限，不表示第三方入站验收通过。** 这些输入均为虚构，不是本机微信的实际消息或故障复现。

327保留首次脚本的1失败/2错误：本地会话要求至少2个连续锚点，而初稿仅给1个；此外固定异常是read_session_stopped，详细原因在report中。已按现有契约修正演练输入及断言，未改产品守卫，328通过。没有为了反例修改或放宽业务代码。

没有产品代码变化，未重跑完整回归或离线安装；上轮369项选定回归仍是321/322，不作为本轮新结果。原4类13项原生夹具继续不跑。真实模型、记忆和发送均未执行。

[330独立复审](evidence/330-source-audit-review.json)核验8份源文件哈希/大小、12项离线检查和结论范围后无剩余发现，没有独立访问实机或联网。[329只读状态](evidence/329-source-audit-checkpoint.json)原监听活动9326次/9262次最小化、unknown1、0超时、防待机活动，未重启或操作窗口。

## 当前决定与后续条件

不安装或接入这两条已查路径，不把其sender/ID字段包装成已验证消息。保留现有最小化只读监听和防待机，用户不需要重发同一输入。

在维持全部现有约束时，当前没有可继续实现接受分支的可靠来源；继续累积unknown或再包一层适配器不能解决。若要改变接入路线或允许非最小化，需要用户明确产品取舍。可讨论的下一步是扩大到非UIA结构化来源的静态评估，或保留正常UI但允许可见窗口；两者都不是现成已验证方案，也不构成安装、提取密钥、修改客户端内存或发送授权。真实自动回复仍须功能和方案可审阅后的最终确认。
