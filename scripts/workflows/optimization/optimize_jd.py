#!/usr/bin/env python3
"""本文件检查并优化岗位说明的清晰度、可匹配性和公平性表达。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_text
from talentmatch.quality import audit_job


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit JD clarity, selectivity, fairness, and completeness")
    parser.add_argument("job")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit_job(load_source(args.job))
    lines = ["# JD 质量与合规审计", "", f"质量分：**{result['quality_score']}/100**", "", "## 问题与修订建议", ""]
    if not result["issues"]:
        lines.append("- 未发现规则库可识别的明显问题；仍需由招聘与法务进行人工复核。")
    for issue in result["issues"]:
        lines.append(f"- [{issue['severity']}] {issue['code']}：{issue['advice']}")
    lines.extend(["", "## 建议结构", "", "1. 岗位使命与成功标准", "2. 3-6条核心职责", "3. 精简的必需条件", "4. 明确的加分项", "5. 地点/工时/用工方式/薪酬（政策允许时）", "6. 成长机会与团队信息"])
    write_text("\n".join(lines), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
