#!/usr/bin/env python3
"""本文件汇总候选人与岗位相关的风险管理、合规证据和待确认事项。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.analyze_risk_compliance"))
