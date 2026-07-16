#!/usr/bin/env python3
"""本文件对单份文本中的姓名、联系方式、证件号和地址等个人信息进行脱敏。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.io import InputError, read_text, write_json, write_text
from talentmatch.privacy import redact
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact common contact and identity fields")
    parser.add_argument("input")
    parser.add_argument("--output")
    parser.add_argument("--stats")
    args = parser.parse_args()
    try:
        redacted, counts = redact(read_text(Path(args.input)))
        write_text(redacted, args.output)
        if args.stats:
            write_json(counts, args.stats)
        return 0
    except (InputError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
