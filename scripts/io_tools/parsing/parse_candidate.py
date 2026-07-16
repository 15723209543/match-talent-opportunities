#!/usr/bin/env python3
"""本文件把候选人原始文本保守解析为结构化字段，无法确认的信息保持未知。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.io import InputError, load_source, write_json
from talentmatch.parser import parse_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse candidate text or structured data conservatively")
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        write_json(parse_candidate(load_source(args.input)), args.output)
        return 0
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
