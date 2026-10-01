"""Check built-in OCR with fictional in-memory images only."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from wechat_memory.ocr_check import main

if __name__ == '__main__':
    raise SystemExit(main())
