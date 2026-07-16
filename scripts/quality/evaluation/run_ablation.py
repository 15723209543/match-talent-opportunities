"""本脚本在同一数据集上比较关键词、技能经验、企业侧和完整双向四种方案。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.evaluation import EVALUATION_MODES, evaluate_records
from talentmatch.excel_config import load_metric_config


def main() -> int:
    parser = argparse.ArgumentParser(description="运行四种匹配方案的消融比较")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    config = load_metric_config()
    result = {mode: evaluate_records(records, mode, config, max(1, args.top_k)) for mode in EVALUATION_MODES}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({mode: {key: value for key, value in payload.items() if key not in {"queries", "failures"}} for mode, payload in result.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
