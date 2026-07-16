#!/usr/bin/env python3
"""本文件在匹配前校验候选人与岗位输入的字段、类型和关键约束。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.io import InputError, load_source, write_json
from talentmatch.parser import parse_candidate, parse_job
from talentmatch.validation import validate_candidate, validate_job


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate candidate or job input")
    parser.add_argument("input")
    parser.add_argument("--kind", required=True, choices=["candidate", "job"])
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        source = load_source(args.input)
        result = validate_candidate(parse_candidate(source)) if args.kind == "candidate" else validate_job(parse_job(source))
        result["ok"] = not result["errors"]
        write_json(result, args.output)
        return 0 if result["ok"] else 3
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
