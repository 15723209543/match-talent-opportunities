"""本脚本把未标注JSONL整理成人工评审包，供多名评审独立填写相关性和推荐结果。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="生成人工评审标注包")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--reviewers", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    pack = []
    for index, record in enumerate(records, 1):
        job_ids = [str(job.get("id") or f"job-{job_index + 1}") for job_index, job in enumerate(record.get("jobs", []))]
        pack.append({
            "query_id": record.get("query_id", f"query-{index}"),
            "job_ids": job_ids,
            "review_forms": [{"reviewer_id": f"reviewer-{number + 1}", "relevance_0_to_3": {job_id: None for job_id in job_ids}, "recommended_job_id": None, "notes": ""} for number in range(max(1, args.reviewers))],
        })
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"instructions": "评审者应独立标注；0不相关、1弱相关、2较相关、3高度相关。", "records": pack}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "records": len(pack), "reviewers": max(1, args.reviewers), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
