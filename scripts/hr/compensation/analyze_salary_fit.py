#!/usr/bin/env python3
"""本文件检查候选人薪酬期望与岗位预算区间、结构和福利是否匹配。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.salary_fit"))
