# 普通窗口读取耗时诊断

v0.1.23 沿用有界、脱敏的最近/最慢子调用诊断，已删除 background 专用路径。普通读取阶段为 started、request_read、client_lookup、process_lookup、window_lookup、binding_check、tree_lookup、list_binding、rows_first、visual_capture、binding_final、snapshot_ready、serializing、completed。

visual_capture 表示进入视觉处理阶段，诊断不保存图片/正文/身份；非视觉读取会立即经过这一边界。错误或超时只保留已完成的固定阶段前缀。最慢调用保留一项，相同舍入毫秒保留最早项；旧或不一致阶段记录不解释为新流程成功。

单次预算仍为 8 秒。已绑定联合快照变化最多 3 次子调用，共用原预算；其他错误立即停止。completed 仅表示原生输出完成，不证明会话接受或可回复。历史最小化耗时报告见 [归档](history/READER_TIMING-before-window-open.md)，不再重启旧实验。
