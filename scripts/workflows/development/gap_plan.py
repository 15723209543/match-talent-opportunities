#!/usr/bin/env python3
"""本文件从匹配结果提取关键差距并生成30、60、90天改进计划。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract verified gaps and a 30/60/90-day plan")
    parser.add_argument("result")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = load_source(args.result)
    recommendations = result.get("recommendations", {})
    write_json({
        "verified_gaps": recommendations.get("verified_gaps", []),
        "needs_verification": recommendations.get("needs_verification", []),
        "development_plan": recommendations.get("development_plan", {}),
        "confidence": result.get("confidence", {}),
    }, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
