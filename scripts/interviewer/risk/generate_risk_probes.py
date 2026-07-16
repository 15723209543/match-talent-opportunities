#!/usr/bin/env python3
"""本文件围绕岗位相关风险、合规和关键未知项生成面试核验问题。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("interviewer.risk_probe"))
