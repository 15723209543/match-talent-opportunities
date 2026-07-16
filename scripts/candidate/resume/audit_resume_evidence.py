#!/usr/bin/env python3
"""本文件检查简历证据的具体性、相关性和可核验程度，并提示缺失内容。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("candidate.resume_evidence"))
