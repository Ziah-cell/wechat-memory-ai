# 本地 OCR 可行性检查（v0.1.4）

2026-10-01，继续免费路线。新增 `ocr-check`，验证 Windows 自带中文 OCR 能否识别固定虚构气泡；它不是微信适配器。

后续已完成隔离 RapidOCR 候选比较，字符识别改善但仍有误检/符号漏字，保持需核查，见 [OCR_CANDIDATE.md](OCR_CANDIDATE.md)。本页保留系统 OCR 原始结果。

```powershell
.\scripts\windows.ps1 -Action ocr-check
```

模块入口为 `python -m wechat_memory.ocr_check`，源码入口为 `scripts/ocr-check.py`。无需安装新的第三方包、购买许可或提供 API Key。

## 本机结果

本机已具备中文识别引擎。三个样例均在内存绘制：960×300 像素、两条相同虚构中文和一条字母数字文本，浅色/深色为 24px，大字号为 32px。颜色和字体仅是测试条件，不代表微信真实截图。

| 样例 | 两条中文均精确匹配 | 字母数字精确匹配 | 恰好三行 |
|---|---|---|---|
| 浅色 light | 否 | 否 | 是 |
| 深色 dark | 是 | 是 | 是 |
| 大字号 large | 是 | 否 | 是 |

实际报告为 **`recognition_mismatch`，退出码 3**，见 [53-ocr-local-result.txt](evidence/53-ocr-local-result.txt)。仅调试固定虚构内容，发现“你”可能被拆成“亻尔”、数字 `1` 可能变为 `I`。临时进行的 2 倍双三次放大实验没有解决字母数字混淆，因此未加入正式实现。正式检查保持原始输入和严格匹配。

这说明免费本地 OCR 在该电脑可执行，**不说明聊天识别可靠，也不证明联系人身份、消息方向、新旧消息或跨重启去重已解决**。重复文字能否识别，与真实消息是否拥有两个不同 ID 是不同问题。不能用昵称、文字散列、气泡坐标或 OCR 结果替代稳定身份/消息标识。

## 实现范围

- Windows PowerShell 5.1 调用系统 `Windows.Media.Ocr.OcrEngine`，只创建进程内 GDI 位图并转换为 SoftwareBitmap；不捕获屏幕/窗口，不接受外部图片、路径、文本或窗口参数。
- 严格核验中文重复行、字母数字和行数。仅忽略 OCR 插入的空白，不猜测 `I/1` 等字符。
- Python 父进程默认 15 秒总超时，可终止子进程；单次 WinRT 操作等待最多 5 秒。输出只接受固定状态和布尔字段；异常正文和识别文本不输出。
- 在个人配置处理之前分流；不读取配置、凭据、数据库或真实聊天，不联网，不创建图片文件、自启动或计划任务。临时子进程在命令结束时退出。
- `synthetic_only=true`；`screen_captured/real_chat_read/network_used/identity_verified/listener_ready/real_send_supported` 固定为 false。核心适配器与发送边界保持原状。

## 状态与退出码

| 状态 | 含义 |
|---|---|
| passed | 三个固定样例的九项检查均通过，仅代表样例；退出码 0 |
| recognition_mismatch | 引擎可运行，但至少一项识别不匹配；退出码 3 |
| language_unavailable | Windows 没有可匹配的中文 OCR 语言，本命令不安装语言包 |
| ocr_unavailable | 原生 API 初始化、识别或资源处理失败，异常不输出 |
| check_timeout / check_failed | 子进程超时或启动/运行失败 |
| invalid_check_output | 返回格式或状态/布尔值组合不符合契约 |
| unsupported_platform / invalid_arguments | 系统不支持或超时参数无效 |

除 passed 外全部退出码 3。`chinese_available=false` 在 API 失败时也可能出现，只有 language_unavailable 才明确表示语言不可用。

## 验证与未通过项

- 测试先行：[49 缺失模块](evidence/49-ocr-check-red.txt)。首次原生识别暴露错误假设：[50 样例未全部匹配](evidence/50-ocr-check-targeted.txt)。测试契约随后改为验证实际结果、保留失败，而非要求系统 OCR 必须全对；分项报告先失败：[51](evidence/51-ocr-detail-red.txt)。
- 新增 **11 项**测试：[52](evidence/52-ocr-check-targeted.txt)，包含真正调用 Windows OCR、移除所有虚构文字后不得通过、实际超时终止、输出脱敏、双 PowerShell 入口及无效个人配置隔离。
- 完整回归 **108/108，27.490 秒，0 失败/错误/跳过**：[54](evidence/54-ocr-stage-regression.txt)。测试通过表示程序如实报告识别失败，不表示 OCR 样例全部通过。
- 0.1.4 wheel 临时构建、隔离安装，三个 PS1 资源完整；安装后同样返回 recognition_mismatch/3：[55](evidence/55-ocr-package.json)。无第三方运行依赖安装、无交付 ZIP。
- 独立审查没有待修复发现，审查者另行通过 11 项定向测试和 diff 检查；这不替代真实微信兼容验证。

本轮曾计划只读检查真实微信的 MSAA 根结构，以排除 UIA 接口遗漏；命令在执行前被自动审批拒绝，返回 `blocked by policy`，未提供更具体原因。没有重试同等操作，没有获得 MSAA 实测结果。该执行限制不能证明微信支持或不支持 MSAA。

上一轮真实 UIA 阻塞仍成立，见 [LIVE_UIA_CHECK.md](LIVE_UIA_CHECK.md)。后续要取得正常可访问的身份与消息来源证据，才可开发真实监听；OCR 研究不能自动解除该前提。不重复要求已完成登录准备的用户再次登录。

## 一手依据

语言检测、RecognizeAsync 和文字/坐标输出见 [Microsoft OcrEngine 文档](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine)。另一条未执行的正常可访问性接口参考 [AccessibleObjectFromWindow](https://learn.microsoft.com/en-us/windows/win32/api/oleacc/nf-oleacc-accessibleobjectfromwindow)。API 文档不构成微信兼容声明。
