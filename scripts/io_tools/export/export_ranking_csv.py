#!/usr/bin/env python3
"""本文件把排序结果安全导出为CSV，并防止表格公式注入。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import csv
from pathlib import Path

from talentmatch.io import load_source, safe_csv_cell


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ranking JSON to formula-safe UTF-8 CSV")
    parser.add_argument("ranking")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = load_source(args.ranking)
    if isinstance(data, dict) and "ready_for_review" in data:
        rows = (
            data.get("ready_for_review", [])
            + data.get("needs_more_data", [])
            + data.get("unverified_hard_requirements", [])
            + data.get("hard_failures", [])
        )
    else:
        rows = data.get("ranking", data if isinstance(data, list) else [])
    fields = ["rank", "candidate_id", "job_id", "status", "overall", "provisional_overall", "recruiter", "candidate", "confidence", "band", "hard_failures"]
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_csv_cell(row.get(key, "")) for key in fields})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
