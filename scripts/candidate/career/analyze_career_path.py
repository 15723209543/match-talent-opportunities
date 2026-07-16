#!/usr/bin/env python3
"""本文件分析岗位方向与求职者职业目标、期望职级和长期发展路径的契合度。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("candidate.career_path"))
