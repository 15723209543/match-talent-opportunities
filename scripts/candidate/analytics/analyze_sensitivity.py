#!/usr/bin/env python3
"""本文件供求职者查看指标系数变化对岗位匹配结果的影响，帮助识别结论是否稳定。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("candidate.sensitivity_analysis"))
