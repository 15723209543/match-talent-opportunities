#!/usr/bin/env python3
"""本文件帮助面试官检查岗位条件和面试问题中的偏见与受保护属性风险。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("interviewer.bias_check"))
