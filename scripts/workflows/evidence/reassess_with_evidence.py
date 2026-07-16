"""本脚本从JSON文件准备证据确认清单，或合并补充证据并输出重评前后对比。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.evidence_loop import prepare_evidence_review, reassess_with_evidence


def _read(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="准备证据核验清单或补证后重评")
    parser.add_argument("--candidate", required=True, help="候选人JSON")
    parser.add_argument("--job", required=True, help="岗位JSON")
    parser.add_argument("--evidence-update", help="补证JSON；省略时只生成确认清单")
    parser.add_argument("--output", required=True, help="输出JSON")
    args = parser.parse_args()
    candidate, job = _read(args.candidate), _read(args.job)
    payload = reassess_with_evidence(candidate, job, _read(args.evidence_update)) if args.evidence_update else prepare_evidence_review(candidate, job)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "stage": payload["stage"], "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
