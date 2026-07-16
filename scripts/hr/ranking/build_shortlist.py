#!/usr/bin/env python3
"""本文件根据同一指标配置生成候选人短名单，并保留人工复核所需依据。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("hr.shortlist"))
