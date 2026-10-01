"""Dependency-free source checkout launcher; safe for Windows multiprocessing spawn."""
from pathlib import Path
import sys

if sys.version_info < (3,11):
    raise SystemExit('Python 3.11+ is required.')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wechat_memory.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
