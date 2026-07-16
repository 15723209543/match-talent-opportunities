#!/usr/bin/env python3
"""本文件识别工作偏好与岗位供给的错配信号，供沟通改善使用而非预测离职。"""

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))
from talentmatch.persona_cli import run_action


if __name__ == "__main__":
    raise SystemExit(run_action("talent_manager.retention_signals"))
