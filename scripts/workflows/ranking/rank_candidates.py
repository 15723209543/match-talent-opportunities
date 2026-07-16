#!/usr/bin/env python3
"""本文件使用统一配置对多名候选人进行通用排序。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.batch import triage_candidates
from talentmatch.io import InputError, load_collection, load_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank candidates for one job using a shared rubric")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--metrics", "--weights", dest="metrics", help="自定义匹配指标 Excel")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        write_json(triage_candidates(load_collection(args.candidates), load_source(args.job), args.metrics), args.output)
        return 0
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
