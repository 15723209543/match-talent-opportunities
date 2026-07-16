#!/usr/bin/env python3
"""本文件执行多名候选人与多个岗位的批量匹配矩阵计算。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.batch import match_matrix
from talentmatch.io import InputError, load_collection, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a candidate-job match matrix")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--metrics", "--weights", dest="metrics", help="自定义匹配指标 Excel")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        write_json(match_matrix(load_collection(args.candidates), load_collection(args.jobs), args.metrics), args.output)
        return 0
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
