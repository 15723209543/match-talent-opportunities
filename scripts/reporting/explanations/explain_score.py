#!/usr/bin/env python3
"""本文件解释匹配分数的指标贡献、归一权重、证据和优先核验项。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse

from talentmatch.io import load_source, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="不重新计算，解释已有匹配结果的逐项贡献")
    parser.add_argument("result")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = load_source(args.result)
    scores = result.get("scores", {})
    lines = ["# 分数解释", "", f"综合分 {scores.get('overall')}，企业侧 {scores.get('recruiter')}，求职者侧 {scores.get('candidate')}。", "", "## 企业侧贡献", ""]
    lines.extend(
        f"- {d['name']}: 得分 {d['score'] if d.get('score') is not None else 'unknown'}，Excel系数 {d.get('coefficient')}，归一权重 {d.get('normalized_weight_percent')}%，贡献 {d['contribution'] if d.get('contribution') is not None else '不计入'}"
        for d in result.get("recruiter_dimensions", [])
    )
    lines.extend(["", "## 求职者侧贡献", ""])
    lines.extend(
        f"- {d['name']}: 得分 {d['score'] if d.get('score') is not None else 'unknown'}，Excel系数 {d.get('coefficient')}，归一权重 {d.get('normalized_weight_percent')}%，贡献 {d['contribution'] if d.get('contribution') is not None else '不计入'}"
        for d in result.get("candidate_dimensions", [])
    )
    lines.extend(["", f"置信度：{result.get('confidence', {}).get('score')}。unknown 默认不计入分母，并通过置信度提示补证。", "", f"综合分采用 Excel 合成系数 {result.get('method', {}).get('overall_coefficients', {})} 的加权调和平均；硬性失败时封顶 49.00。"])
    write_text("\n".join(lines), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
