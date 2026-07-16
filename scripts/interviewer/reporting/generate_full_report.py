#!/usr/bin/env python3
"""本文件生成面向面试官的完整报告，包含问题计划、评分关注点和公平性提醒。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("interviewer.full_report"))
