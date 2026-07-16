"""本模块把通用匹配结果整理为兼容旧流程的Markdown报告。"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List

from .persona_reporting import _markdown_list, _markdown_table, _markdown_text


def _fmt(value: Any) -> str:
    """把兼容报告中的任意动态值转成安全单行文本。"""
    return _markdown_text(value, "unknown")


def _number(value: Any, suffix: str = "", default: str = "unknown") -> str:
    """稳健格式化数值；异常类型只按安全文本展示，不让旧导出器崩溃。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _markdown_text(value, default)
    if not math.isfinite(number):
        return default
    return f"{number:.2f}{suffix}"


def _label(value: Any) -> str:
    """从对象中提取适合列表展示的名称，并统一执行Markdown清洗。"""
    if isinstance(value, Mapping):
        for key in ("name", "metric", "focus", "question", "reason", "status"):
            if value.get(key) not in (None, ""):
                return _markdown_text(value.get(key))
        value = json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
    return _markdown_text(value, "unknown")


def _values(value: Any) -> List[Any]:
    """把字符串、映射或可迭代值统一成列表，避免逐字符拼接。"""
    if value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _joined_labels(value: Any, empty: str = "无") -> str:
    """生成经过清洗的顿号分隔摘要。"""
    labels = [_label(item) for item in _values(value)]
    return "、".join(labels) if labels else empty


def _public_score(value: Any) -> str:
    """把未达到正式比较条件的空分数显示为明确的中文状态。"""
    return "暂不可比较" if value is None else _number(value, "/100")


def to_markdown(result: Dict[str, Any]) -> str:
    """生成旧版兼容报告，所有动态字段均复用角色报告的安全Markdown渲染函数。"""
    if not isinstance(result, Mapping):
        raise ValueError("result_must_be_object")
    score = result.get("scores", {})
    confidence = result.get("confidence", {})
    if not isinstance(score, Mapping):
        score = {}
    if not isinstance(confidence, Mapping):
        confidence = {}
    lines: List[str] = [
        "# 双向人岗匹配报告",
        "",
        "## 1. 执行结论",
        "",
        f"- 综合匹配：**{_public_score(score.get('overall'))} ({_fmt(score.get('band'))})**",
        f"- 企业侧适配：{_public_score(score.get('recruiter'))}",
        f"- 求职者侧适配：{_public_score(score.get('candidate'))}",
        f"- 置信度：{_number(confidence.get('score', 0), '/100')} ({_fmt(confidence.get('level'))})",
        f"- 结论：{_fmt(result.get('executive_summary', ''))}",
        "",
        "## 2. 硬性条件核验",
        "",
    ]
    gates = [gate for gate in _values(result.get("gates", [])) if isinstance(gate, Mapping)]
    if gates:
        lines.extend(_markdown_table(
            ["条件", "状态", "证据"],
            [[gate.get("gate"), gate.get("status"), gate.get("evidence", gate.get("evidence_rank"))] for gate in gates],
        ).splitlines())
    else:
        lines.append("未发现被明确标记为 hard 的条件。")
    lines.extend(["", "## 3. 企业侧适配", ""])
    for item in _values(result.get("recruiter_dimensions", [])):
        if not isinstance(item, Mapping):
            lines.append(f"- {_label(item)}")
            continue
        metric_score = "unknown" if item.get("score") is None else _number(item.get("score"), "/100")
        contribution = "不计入" if item.get("contribution") is None else _number(item.get("contribution"))
        lines.append(f"- {_fmt(item.get('name'))}：{metric_score}，Excel系数 {_number(item.get('coefficient'))}，归一权重 {_number(item.get('normalized_weight_percent'), '%')}，贡献 {contribution}")
    lines.extend(["", "## 4. 求职者侧适配", ""])
    for item in _values(result.get("candidate_dimensions", [])):
        if not isinstance(item, Mapping):
            lines.append(f"- {_label(item)}")
            continue
        metric_score = "unknown" if item.get("score") is None else _number(item.get("score"), "/100")
        contribution = "不计入" if item.get("contribution") is None else _number(item.get("contribution"))
        lines.append(f"- {_fmt(item.get('name'))}：{metric_score}，Excel系数 {_number(item.get('coefficient'))}，归一权重 {_number(item.get('normalized_weight_percent'), '%')}，贡献 {contribution}")
    evidence_rows = []
    for row in _values(result.get("evidence_matrix", [])):
        if not isinstance(row, Mapping):
            continue
        evidence_rows.append([
            row.get("type"),
            row.get("requirement"),
            row.get("status"),
            _number(row.get("item_score", 0)),
            str(row.get("evidence", ""))[:100],
        ])
    lines.extend(["", "## 5. 证据矩阵", ""])
    lines.extend(_markdown_table(["类型", "要求", "状态", "得分", "证据"], evidence_rows).splitlines())
    rec = result.get("recommendations", {})
    if not isinstance(rec, Mapping):
        rec = {}
    lines.extend(["", "## 6. 缺口与风险", ""])
    lines.append("- 已核实缺口：" + _joined_labels(rec.get("verified_gaps", [])))
    lines.append("- 待核实信息：" + _joined_labels(rec.get("needs_verification", [])))
    lines.extend(["", "## 7. 下一步行动", ""])
    resume_actions = _values(rec.get("resume_actions", []))[:5]
    if resume_actions:
        lines.extend(_markdown_list(resume_actions).splitlines())
    development_plan = rec.get("development_plan", {})
    if isinstance(development_plan, Mapping):
        for phase, actions in development_plan.items():
            lines.append(f"- {_fmt(phase)}：{_joined_labels(actions, '待补')}")
    method = result.get("method", {})
    if not isinstance(method, Mapping):
        method = {}
    coefficients = method.get("overall_coefficients", {})
    if not isinstance(coefficients, Mapping):
        coefficients = {}
    lines.extend([
        "",
        "## 8. 方法说明",
        "",
        f"综合分采用企业侧系数 {_fmt(coefficients.get('overall_recruiter'))} 与求职者侧系数 {_fmt(coefficients.get('overall_candidate'))} 的加权调和平均；所有指标影响系数均来自 Excel，unknown 按每行配置的缺失策略处理。只有明确 hard 且失败的条件会把综合分封顶为 49。此报告仅用于辅助人工判断，不应自动决定录用、淘汰、晋升或薪酬。",
    ])
    return "\n".join(lines) + "\n"
