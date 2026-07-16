#!/usr/bin/env python3
"""本文件针对缺失、薄弱或相互矛盾的证据生成核验问题。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("interviewer.evidence_probe"))
