"""Source-tree entry point for the independent read-only WeChat connection."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wechat_memory.live_read import main

if __name__ == '__main__':
    raise SystemExit(main())
