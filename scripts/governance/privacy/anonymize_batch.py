#!/usr/bin/env python3
"""本文件批量遍历结构化资料并脱敏可识别个人身份的信息。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_json
from talentmatch.privacy import redact_object


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact PII recursively from a JSON/JSONL/CSV batch")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_json(redact_object(load_source(args.input)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
