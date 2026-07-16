#!/usr/bin/env python3
"""本文件综合分析办公方式、协作方式、节奏和管理偏好等工作风格匹配情况。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("candidate.analyze_workstyle"))
