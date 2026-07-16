#!/usr/bin/env python3
"""本文件自动发现并运行全部回归测试，输出可用于提交前验收的测试汇总。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))


def main() -> int:
    """发现test_*.py并以详细模式执行。"""
    suite = unittest.defaultTestLoader.discover(str(TEST_DIR), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
