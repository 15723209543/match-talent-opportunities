#!/usr/bin/env python3
"""本文件根据岗位要求和真实经历证据给出简历表达改进建议。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evidence-safe resume optimization advice")
    parser.add_argument("result")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = load_source(args.result)
    rec = result.get("recommendations", {})
    lines = ["# 简历优化建议", "", "> 只写真实、可核验的经历；不得为了匹配分虚构技能、年限或指标。", "", "## 优先修改", ""]
    lines.extend(f"- {action}" for action in rec.get("resume_actions", []))
    lines.extend(["", "## 待补证据", ""])
    lines.extend(f"- {item}" for item in rec.get("needs_verification", []))
    lines.extend(["", "## 不应伪装的缺口", ""])
    lines.extend(f"- {item}" for item in rec.get("verified_gaps", []))
    lines.extend(["", "## 推荐要点句式", "", "- 在【业务背景】下，负责【个人行动】，通过【方法/工具】实现【量化结果】，并说明【范围/时间】。"])
    write_text("\n".join(lines), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
