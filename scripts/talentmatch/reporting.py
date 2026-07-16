"""本模块把通用匹配结果整理为兼容旧流程的Markdown报告。"""

from __future__ import annotations

from typing import Any, Dict, List


def _fmt(value: Any) -> str:
    return "unknown" if value is None else str(value)


def _public_score(value: Any) -> str:
    """把未达到正式比较条件的空分数显示为明确的中文状态。"""
    return "暂不可比较" if value is None else f"{float(value):.2f}/100"


def to_markdown(result: Dict[str, Any]) -> str:
    score = result.get("scores", {})
    confidence = result.get("confidence", {})
    lines: List[str] = [
        "# 双向人岗匹配报告",
        "",
        "## 1. 执行结论",
        "",
        f"- 综合匹配：**{_public_score(score.get('overall'))} ({score.get('band', 'unknown')})**",
        f"- 企业侧适配：{_public_score(score.get('recruiter'))}",
        f"- 求职者侧适配：{_public_score(score.get('candidate'))}",
        f"- 置信度：{confidence.get('score', 0):.2f}/100 ({confidence.get('level', 'unknown')})",
        f"- 结论：{result.get('executive_summary', '')}",
        "",
        "## 2. 硬性条件核验",
        "",
    ]
    gates = result.get("gates", [])
    if gates:
        lines.extend(["| 条件 | 状态 | 证据 |", "|---|---|---|"])
        for gate in gates:
            lines.append(f"| {gate.get('gate')} | {gate.get('status')} | {_fmt(gate.get('evidence', gate.get('evidence_rank')))} |")
    else:
        lines.append("未发现被明确标记为 hard 的条件。")
    lines.extend(["", "## 3. 企业侧适配", ""])
    for item in result.get("recruiter_dimensions", []):
        metric_score = "unknown" if item.get("score") is None else f"{item['score']:.2f}/100"
        contribution = "不计入" if item.get("contribution") is None else f"{item['contribution']:.2f}"
        lines.append(f"- {item['name']}: {metric_score}，Excel系数 {item['coefficient']:.2f}，归一权重 {item['normalized_weight_percent']:.2f}%，贡献 {contribution}")
    lines.extend(["", "## 4. 求职者侧适配", ""])
    for item in result.get("candidate_dimensions", []):
        metric_score = "unknown" if item.get("score") is None else f"{item['score']:.2f}/100"
        contribution = "不计入" if item.get("contribution") is None else f"{item['contribution']:.2f}"
        lines.append(f"- {item['name']}: {metric_score}，Excel系数 {item['coefficient']:.2f}，归一权重 {item['normalized_weight_percent']:.2f}%，贡献 {contribution}")
    lines.extend(["", "## 5. 证据矩阵", "", "| 类型 | 要求 | 状态 | 得分 | 证据 |", "|---|---|---|---:|---|"])
    for row in result.get("evidence_matrix", []):
        evidence = str(row.get("evidence", "")).replace("|", "\\|").replace("\n", " ")[:100]
        lines.append(f"| {row.get('type')} | {str(row.get('requirement', '')).replace('|', '/')} | {row.get('status')} | {row.get('item_score', 0)} | {evidence} |")
    rec = result.get("recommendations", {})
    lines.extend(["", "## 6. 缺口与风险", ""])
    lines.append("- 已核实缺口：" + ("、".join(rec.get("verified_gaps", [])) or "无"))
    lines.append("- 待核实信息：" + ("、".join(rec.get("needs_verification", [])) or "无"))
    lines.extend(["", "## 7. 下一步行动", ""])
    for action in rec.get("resume_actions", [])[:5]:
        lines.append(f"- {action}")
    for phase, actions in rec.get("development_plan", {}).items():
        lines.append(f"- {phase}: " + "；".join(actions))
    lines.extend([
        "",
        "## 8. 方法说明",
        "",
        f"综合分采用企业侧系数 {result.get('method', {}).get('overall_coefficients', {}).get('overall_recruiter', 'unknown')} 与求职者侧系数 {result.get('method', {}).get('overall_coefficients', {}).get('overall_candidate', 'unknown')} 的加权调和平均；所有指标影响系数均来自 Excel，unknown 按每行配置的缺失策略处理。只有明确 hard 且失败的条件会把综合分封顶为 49。此报告仅用于辅助人工判断，不应自动决定录用、淘汰、晋升或薪酬。",
    ])
    return "\n".join(lines) + "\n"
