#!/usr/bin/env python3
"""本文件汇总人员技能、熟练度、使用年限和证据，形成可核验的技能盘点。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("talent_manager.skill_inventory"))
