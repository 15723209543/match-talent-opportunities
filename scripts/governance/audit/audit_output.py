#!/usr/bin/env python3
"""本文件审计匹配结果的分值范围、必要说明、隐私风险和输出结构是否合规。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.audit import audit_output
from talentmatch.io import load_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a match result for bounds, gate cap, PII, and notices")
    parser.add_argument("result")
    parser.add_argument("--output")
    args = parser.parse_args()
    audit = audit_output(load_source(args.result))
    write_json(audit, args.output)
    return 0 if audit["ok"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
