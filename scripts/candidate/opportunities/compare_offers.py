#!/usr/bin/env python3
"""本文件帮助求职者并列比较多个录用机会的匹配得分、条件和待确认事项。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("candidate.compare_offers"))
