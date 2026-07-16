#!/usr/bin/env python3
"""本文件比较两份匹配结果，定位分数、指标配置和结论发生变化的原因。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two match results after profile/JD changes")
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--output")
    args = parser.parse_args()
    old, new = load_source(args.old), load_source(args.new)
    def delta(key: str):
        old_value, new_value = old.get("scores", {}).get(key), new.get("scores", {}).get(key)
        return None if old_value is None or new_value is None else round(float(new_value) - float(old_value), 2)

    score_delta = {key: delta(key) for key in ("overall", "provisional_overall", "recruiter", "candidate")}
    old_gaps = set(old.get("recommendations", {}).get("explicit_requirement_gaps", []))
    new_gaps = set(new.get("recommendations", {}).get("explicit_requirement_gaps", []))
    write_json({"old_status": old.get("scores", {}).get("status"), "new_status": new.get("scores", {}).get("status"), "score_delta": score_delta, "resolved_gaps": sorted(old_gaps - new_gaps), "new_gaps": sorted(new_gaps - old_gaps), "confidence_delta": round(new.get("confidence", {}).get("score", 0) - old.get("confidence", {}).get("score", 0), 2)}, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
