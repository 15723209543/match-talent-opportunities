#!/usr/bin/env python3
"""本文件把结构化匹配结果导出为便于阅读和分享的Markdown报告。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_text
from talentmatch.reporting import to_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a result JSON as Markdown")
    parser.add_argument("result")
    parser.add_argument("--output")
    args = parser.parse_args()
    write_text(to_markdown(load_source(args.result)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
