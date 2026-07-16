#!/usr/bin/env python3
"""本文件检查岗位或简历文本中的受保护属性、歧视性条件和嵌入式指令风险。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.fairness import audit_text
from talentmatch.io import InputError, read_text, write_json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Flag protected-trait criteria and embedded instructions")
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        write_json(audit_text(read_text(Path(args.input))), args.output)
        return 0
    except (InputError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
