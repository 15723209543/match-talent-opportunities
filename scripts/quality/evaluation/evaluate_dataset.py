"""本脚本读取已标注JSONL数据集，输出Top-K、NDCG、排序一致性和失败处理指标。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.evaluation import EVALUATION_MODES, evaluate_records
from talentmatch.excel_config import load_metric_config


def _records(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                value.setdefault("query_id", f"line-{line_number}")
                yield value


def main() -> int:
    parser = argparse.ArgumentParser(description="离线评测人岗匹配数据集")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--mode", choices=EVALUATION_MODES, default="full")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate_records(_records(Path(args.dataset)), args.mode, load_metric_config(), max(1, args.top_k))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"queries", "failures"}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
