#!/usr/bin/env python3
"""本文件根据匹配证据、低分项和未知项生成通用结构化面试计划。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Create evidence-based interview questions from a match")
    parser.add_argument("result")
    parser.add_argument("--side", choices=["candidate", "recruiter"], default="candidate")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = load_source(args.result)
    questions = result.get("recommendations", {}).get("interview_questions", [])
    if args.side == "candidate":
        framing = "使用STAR/CARE结构准备回答，明确个人贡献和量化结果。"
    else:
        framing = "向所有候选人使用相同核心问题和评分锚点，并为合理追问留出空间。"
    write_json({"side": args.side, "framing": framing, "questions": questions, "prohibited": ["受保护属性问题", "要求披露与工作无关的健康或家庭信息"]}, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
