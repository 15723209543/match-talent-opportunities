#!/usr/bin/env python3
"""本文件从招聘视角分析候选人的责任担当、交付、协作和问题解决等行为证据。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.analyze_behavior"))
