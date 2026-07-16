#!/usr/bin/env python3
"""本文件汇总团队共同能力缺口，形成培训主题和优先级建议。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("talent_manager.training_priorities"))
