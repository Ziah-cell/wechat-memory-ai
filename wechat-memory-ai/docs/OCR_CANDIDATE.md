# 免费本地 OCR 候选实测

日期：2026-10-01。核心应用仍为 v0.1.4；本阶段增加一个独立的源码树候选实验，不改默认适配器、模型、记忆或发送行为。

## 结果

RapidOCR 正确识别了三个原始样例里的重复中文与 `TEST12345`，改善了 Windows OCR 的字符误读。但浅色/大字号样例多识别出气泡边缘的下划线；提高阈值虽能过滤这些误检，也会漏掉另外一张样例中真正的下划线。因此最终报告为 **`review_required` / 退出码 3**，不能接入自动消息处理。

| 固定虚构样例 | 原始返回行数 | ≥0.9 的行数 | 不确定行数 | 原始文字全部匹配 | 过滤后全部匹配 | 需核查 |
|---|---:|---:|---:|---|---|---|
| 浅色 light | 4 | 3 | 1 | 否 | 是 | 是 |
| 深色 dark | 3 | 3 | 0 | 是 | 是 | 否 |
| 大字号 large | 4 | 3 | 1 | 否 | 是 | 是 |
| 无文字 blank | 0 | 0 | 0 | 是 | 是 | 否 |
| 真实符号 symbol | 3 | 2 | 1 | 是 | 否 | 是 |

最终原始报告：[63-ocr-candidate-final.json](evidence/63-ocr-candidate-final.json)。只要存在低置信度返回项，或结果不匹配，就保持需核查。`accepted` 仅表示达到实验阈值，不代表已经批准作为真实消息。置信度不是正确率，五张图也不是实际微信准确率评估。

Windows 自带 OCR 的补充实验中，黑白化与 1/2/3 倍放大均未消除字母数字误读；本机 en-US 和 zh-Hant OCR 语言不可用，没有安装系统语言包。保留 v0.1.4 原始失败结果，见 [OCR_CHECK.md](OCR_CHECK.md)。

## 现在如何运行

本机已经在项目 `.ocr-env` 隔离目录安装候选依赖，无需重复安装。在 `wechat-memory-ai` 目录运行：

```powershell
& .\.ocr-env\Scripts\python.exe scripts/ocr-candidate-check.py
```

也可用原有 Python 启动该脚本，它会选择项目已有 `.ocr-env` 的解释器作为子进程；`--python` 可以显式指定实验解释器。缺少依赖时返回固定错误，不自动联网安装。

该脚本只用于源码树中的固定样例，没有加入默认 `windows.ps1` 运行流程，也不打包进应用 wheel。核心与单元测试仍只依赖标准库；真实候选推理通过独立命令实测。

## 实际依赖与来源

- RapidOCR **3.9.2**、ONNX Runtime **1.30.0**、OmegaConf **2.3.1**；本机 Python 3.12 / Windows x64。23 个实验运行依赖及发行文件 SHA 固定在 [requirements-ocr.lock](../requirements-ocr.lock)，实际环境证据见 [59](evidence/59-rapidocr-environment.json)。`pip check` 无依赖冲突。
- 最初只允许 wheel 时，解析器退回 OmegaConf 2.0.0，实测不支持 RapidOCR 使用的 WindowsPath。已在实验环境改为 2.3.1；ANTLR 4.9.3 从官方 PyPI 源码包构建。锁文件覆盖运行包与其来源哈希，不宣称锁定了临时构建工具。
- 本机从 PyPI 下载了实验软件和包内模型；这与之后的离线推理是两个阶段。未购买许可、改系统 Python 或安装系统级软件。
- RapidOCR 声明代码 Apache-2.0，模型版权归 PaddleOCR 对应权利方；[代码许可证](https://github.com/RapidAI/RapidOCR/blob/549847df506a32421086d2a08d19646ee958a6e0/LICENSE)、[模型来源和哈希清单](https://github.com/RapidAI/RapidOCR/blob/549847df506a32421086d2a08d19646ee958a6e0/python/MODEL_LICENSES.md)。实际三个包内 ONNX 的 SHA 与清单一致。ONNX Runtime 的许可见 [Microsoft LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)。
- 环境、缓存、模型和第三方二进制均被 Git 忽略，不随本阶段提交分发。提交的五张 PNG 是项目生成的虚构测试素材。

如果以后在另一台相同平台机器重建实验环境，可用有效 Python 创建 `.ocr-env`，再用 pip 对该环境安装 `--require-hashes -r requirements-ocr.lock`；不要把候选依赖安装到默认核心环境，也不要跳过实际识别检查。

## 执行与数据范围

父进程默认 30 秒超时，直接用字面参数启动 `python -I` 子进程；超时终止。不接受外部图片、屏幕、窗口、配置、聊天或凭据输入。五张固定图片和三份模型必须通过大小/SHA 校验。

模型本地加载，两个 CPU 推理线程；禁用 ONNX Runtime 遥测，Python 审计钩子阻止出站连接/DNS和 bind。实际出站尝试为 **0**；阻止了 **1** 次 urllib3 导入时的本地 IPv6 bind 能力探测。该机制不是操作系统网络沙箱，未做完整系统流量抓包，不把 Python 审计当作对任意原生库联网行为的保证。

SDK 的识别置信度过滤显式设为 `0.0` 并核验生效，让低于 SDK 默认 0.5 的识别返回项也参与不确定性统计。文本检测器本身仍可能漏检，本脚本无法把未检测到的内容恢复出来。

报告仅包含固定状态、计数、布尔值和固定依赖版本；识别文本、第三方输出和异常正文不转发。`identity_verified/listener_ready/real_send_supported/real_chat_read/screen_captured` 始终 false。整个候选实验没有连接 Engine、SQLite 或实际微信。

## 验证和剩余阻塞

测试先行：[56](evidence/56-ocr-candidate-red.txt)。初次 7 项测试：[57](evidence/57-ocr-candidate-targeted.txt)。独立审查发现 SDK 提前过滤低分结果和报告一致性校验遗漏，先补失败回归：[60](evidence/60-ocr-candidate-review-red.txt)，两处修复后 **9 项定向测试通过**：[61](evidence/61-ocr-candidate-review-fixed.txt)，审查复验已关闭两项问题。完整回归 **117/117，28.766 秒，0 失败/错误/跳过**，见 [62](evidence/62-ocr-candidate-regression.txt)。

桌面 Computer Use 模块本轮可用，但返回的 5 个可定位窗口中没有微信。没有启动或操作微信、重新登录、读取聊天、发送或再次尝试被拒绝的 MSAA 检查。此结果只说明该次窗口清单未提供微信目标，不等于确认账号离线。

真实自动接入仍需正常可访问的稳定联系人身份、新消息来源与去重边界。OCR 改善字符识别不能替代这些证据。若改做逐条人工核对的草稿流程，需要明确改变交互方式，不能把这种方式称为已完成的全自动普通微信聊天。
