#!/usr/bin/env python3
"""本文件整理个人或团队能力矩阵，展示已具备能力、缺口与证据覆盖。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("talent_manager.capability_matrix"))
