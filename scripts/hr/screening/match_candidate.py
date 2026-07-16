#!/usr/bin/env python3
"""本文件从招聘视角执行候选人与岗位的双向匹配并生成角色化结果。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.match_candidate"))
