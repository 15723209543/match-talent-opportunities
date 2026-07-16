#!/usr/bin/env python3
"""本文件比较候选人工作偏好与团队文化、管理方式和协作环境的契合度。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.analyze_culture_fit"))
