#!/usr/bin/env python3
"""本文件校验指标Excel的结构、80项指标数量、系数范围和唯一性。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import json

from talentmatch.excel_config import load_metric_config, validate_metric_config


def main() -> int:
    parser = argparse.ArgumentParser(description="校验可编辑的匹配指标 Excel")
    parser.add_argument("metrics", nargs="?", help="xlsx 路径；省略时校验项目内默认文件")
    args = parser.parse_args()
    errors = validate_metric_config(args.metrics)
    payload = {"ok": not errors, "errors": errors}
    if not errors:
        config = load_metric_config(args.metrics)
        payload.update({"metric_count": config["metric_count"], "sha256": config["sha256"], "source": config["source"]})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 3


if __name__ == "__main__":
    raise SystemExit(main())
