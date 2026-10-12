# 普通窗口监听的防自动待机

正常打开窗口方案仍保留显式 `-KeepAwake` / `--keep-awake`，默认关闭，监听结束后释放。它不修改电源计划、不让最小化受到支持，也不保证锁屏、合盖或手动睡眠期间继续读取。

```powershell
.\scripts\windows.ps1 -Action start-listener -ListenerData data/open-window-listener -KeepAwake -ClientPath '<本机Weixin.exe路径>'
```

开始/状态/停止必须使用同一数据目录，见 [监听说明](CONTINUOUS_LISTENER.md)。本次未启动监听或申请防待机。此前最小化监听和系统待机时序仅保留在 [历史报告](history/POWER_MANAGEMENT-before-window-open.md)，旧运行命令已删除。
