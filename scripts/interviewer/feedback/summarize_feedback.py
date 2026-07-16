#!/usr/bin/env python3
"""本文件将面试反馈整理为基于证据的摘要，并区分事实、判断和待核验项。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("interviewer.feedback_summary"))
