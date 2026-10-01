"""Run offline tests without installing dependencies or contacting a real service."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(str(root/'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
