# 固定虚构 OCR 样例

五张 PNG 都由本项目的 System.Drawing 绘图代码生成，不是屏幕截图，不含账号或真实聊天。尺寸均为 960×300；字体为 Microsoft YaHei，仅保存渲染后的像素，不分发字体文件。

- light / dark / large：冻结 `src/wechat_memory/ocr_synthetic.ps1` 在本机生成的三种样例像素。两行“中文测试收到你好”和一行 `TEST12345`，与 Windows OCR 比较使用相同 PNG。
- blank：浅色样例保留背景气泡，移除三次 DrawString。
- symbol：浅色样例把 `TEST12345` 换成单个 `_`，用于检查提高置信度阈值是否会漏掉真实符号。

脚本 `scripts/ocr-candidate-check.py` 固定校验五个文件的大小和 SHA-256，不接受其他图片路径；预期文字仅用于比对，不注入模型输入。文件哈希也固定在该脚本中。
