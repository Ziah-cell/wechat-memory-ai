> 2026-10-13：本文保留既往受控测试及普通窗口组件说明。当前用户选定旧测试号，已完成用户确认覆盖状态下的非前台静态读取，真实桥接未完成；最新状态与范围以 [STATUS](STATUS.md)、[窗口验证](OPEN_WINDOW_VALIDATION.md) 为准。最小化路线已删除，旧测试成功不代表当前非前台/遮挡收发成功。

# 2026-10-01 首次登录后的只读 UIA 验证

后续状态已变化：用户再次本人登录后，v0.1.5 独立程序已读取测试窗口的列表和文本，见 [LIVE_READ.md](LIVE_READ.md)。下文保留首次检查的原始结果，不代表当前仍只暴露基础控件。

## 结论

用户已确认本人登录受控的第二个普通个人号，并打开唯一测试好友窗口。**当前会话没有暴露足以支持联系人核验和消息监听的 UIA 控件。** 暂不能将真实来源接入离线核心。

这是本次正常 UIA 读取范围内的结果，不证明所有微信版本、账号或免费路线永久不可用；也没有证据把原因确定为账号权限或具体版本缺陷。用户确认准备完成与程序已验证稳定账号/联系人身份是两回事，后者仍为 false。

## 实际观察

| 项目 | 结果 |
|---|---|
| 客户端文件 | `D:\软件\Weixin\Weixin.exe`，版本 **4.1.15.50** |
| 与此前区别 | 此前检测为 4.1.15.13；本轮没有安装、升级或降级客户端 |
| 精确路径匹配进程 | 5 个 |
| Process.MainWindowHandle | 1 个非零主窗口 |
| Win32 可见顶层窗口 | 同一客户端进程集合内 2 个，均补查结构 |
| 主窗口状态 | 可见、前台、未最小化；在顶层窗口清单内 |
| 两个窗口的结构 | 各 8 个控件，3 个 onscreen；未达到遍历上限，未发生进程范围变化 |
| 控件组成 | Window ×1、Pane ×2、TitleBar ×1、Button ×4 |
| List / ListItem / Text / Edit 等 | 本次树中未观察到 |
| 登录状态 | 用户确认已准备好；探针 `login_state=unverified` |
| 身份 / 监听 / 真实发送 | `identity_verified=false` / `listener_ready=false` / `real_send_supported=false` |

本机 .NET ControlType 常量对应：50032 Window、50033 Pane、50037 TitleBar、50000 Button。仅有这些控件不能证明可定位测试好友或读取消息。`structure_observed` 和退出码 0 只表示结构读取成功，**不是微信消息通道验收通过**。

## 检查方法与证据

1. 运行现有 `.\scripts\windows.ps1 -Action probe-wechat -ClientPath 'D:\软件\Weixin\Weixin.exe'`，结果见 [45-wechat-live-structure-probe.txt](evidence/45-wechat-live-structure-probe.txt)。
2. 只读 Win32 枚举顶层窗口，先按进程 ID 过滤到上述完整客户端路径，再统计可见窗口；使用 IsIconic/GetForegroundWindow 检查主窗口状态。未读取任何窗口标题。结果见 [46-wechat-window-metadata.json](evidence/46-wechat-window-metadata.json)。
3. 从这两个窗口的句柄调用已有 TreeProbe.Read，只读取 ProcessId、ControlType、IsOffscreen。每窗口最多 256 节点、深度 16，诊断子进程总超时 15 秒；不从桌面递归读取。结果见 [47-wechat-owned-window-structures.json](evidence/47-wechat-owned-window-structures.json)。

没有读取 Name、Value、Text、AutomationId、RuntimeId，没有截图、OCR、窗口点击/切换/输入/滚动，没有记录或上传聊天正文、昵称、二维码、PID 或窗口句柄。未启动或重启微信，未发送消息、调用真实模型或修改系统/客户端配置。

## 接下来仍需要的条件

正常 UIA 路线需要客户端向正常可访问性接口提供会话/消息控件，再对当前测试好友做稳定身份、新消息边界和去重验证。当前条件不足，故未实现以猜测控件/昵称为依据的监听器。

不因本次失败自动降级微信、修改内存、提取密钥、修改注册表、启动付费激活或接管登录。OCR 尚未实测；即使可读文字，也不能代替稳定身份/消息证据，不能据此开启自动回复。后续替代路线需要单独核验实际可行性。
