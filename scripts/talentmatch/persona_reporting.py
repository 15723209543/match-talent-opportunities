"""本模块为HR、求职者、面试官和人才发展负责人生成侧重点不同的报告。"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import quote

from .constants import validate_persona
from .visualization import generate_report_charts


ROLE_PROFILE = {
    "hr": {
        "title": "HR候选人筛选与核验报告",
        "subtitle": "先看能否进入人工复核，再看能力证据、硬条件和候选人侧约束。",
        "accent": "#9B2438",
        "side": "recruiter",
    },
    "candidate": {
        "title": "求职者双向匹配与发展报告",
        "subtitle": "既看你是否适合岗位，也看岗位是否适合你的偏好与发展方向。",
        "accent": "#3C78A8",
        "side": "candidate",
    },
    "interviewer": {
        "title": "面试官结构化核验工作单",
        "subtitle": "围绕关键未知项和低分项追问，使用统一评分锚点记录事实。",
        "accent": "#6A4C93",
        "side": "recruiter",
    },
    "talent_manager": {
        "title": "人才发展与内部流动建议报告",
        "subtitle": "区分已知能力差距与证据缺口，形成可验证的30/60/90天计划。",
        "accent": "#2E7D63",
        "side": "candidate",
    },
}


def _metric_rows(items: Iterable[Dict[str, Any]], reverse: bool = True, limit: int = 8) -> List[Dict[str, Any]]:
    """选取有实际评分的指标，供优势或差距列表使用。"""
    known = [item for item in items if item.get("score") is not None]
    return sorted(
        known,
        key=lambda item: (float(item.get("score", 0)), float(item.get("coefficient") or 0)),
        reverse=reverse,
    )[:limit]


def _priority_rows(items: Iterable[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """先列高系数未知项，再列有依据的低分项。"""
    values = list(items)
    unknown = sorted(
        [item for item in values if item.get("effective_score") is None and item.get("status") != "not_applicable"],
        key=lambda item: (-(item.get("coefficient") or 0), str(item.get("id"))),
    )
    low = _metric_rows(values, False, limit)
    return (unknown + low)[:limit]


def _score_value(scores: Dict[str, Any], key: str) -> Any:
    """角色报告只展示正式分；暂估分仅保留在完整JSON和审计结果中。"""
    return scores.get(key)


def _common_payload(result: Dict[str, Any], persona: str) -> Dict[str, Any]:
    profile = ROLE_PROFILE[persona]
    scores = result.get("scores", {})
    side = profile["side"]
    return {
        "audience": persona,
        "report_title": profile["title"],
        "decision_status": scores.get("status"),
        "headline": {
            "overall": scores.get("overall"),
            "recruiter": scores.get("recruiter"),
            "candidate": scores.get("candidate"),
            "confidence": result.get("confidence", {}).get("score"),
            "summary": result.get("executive_summary"),
            "comparability": "可进入人工比较" if scores.get("status") == "ready_for_review" else "暂不可比较",
        },
        "priority_categories": result.get("analytics", {}).get("category_scores", {}).get(side, []),
        "data_sufficiency": scores.get("data_sufficiency", {}),
        "full_match": result,
    }


def build_persona_payload(result: Dict[str, Any], persona: str) -> Dict[str, Any]:
    """按四类角色返回字段不同、可直接供其他平台消费的结构化结果。"""
    persona = validate_persona(persona)
    base = _common_payload(result, persona)
    recruiter_dimensions = result.get("recruiter_dimensions", [])
    candidate_dimensions = result.get("candidate_dimensions", [])
    recommendations = result.get("recommendations", {})
    analytics = result.get("analytics", {})

    if persona == "hr":
        base.update({
            "decision_scope": "用于候选人分流、人工复核和结构化面试准备，不单独作出录用或淘汰决定。",
            "hard_conditions": result.get("gates", []),
            "high_confidence_evidence": _metric_rows(recruiter_dimensions, True, 10),
            "priority_verification": _priority_rows(recruiter_dimensions, 12),
            "candidate_constraints": _priority_rows(candidate_dimensions, 8),
            "manual_review_queue_reasons": [result.get("executive_summary", "")] + result.get("warnings", []),
            "interview_questions": recommendations.get("interview_questions", []),
            "recruiter_actions": recommendations.get("recruiter_actions", []),
            "fairness_notice": result.get("fairness_audit", {}),
        })
    elif persona == "candidate":
        base.update({
            "decision_scope": "用于判断岗位、完善真实材料和准备面试，不替代个人职业决策。",
            "mutual_fit_summary": analytics.get("score_balance", {}),
            "my_evidence_strengths": _metric_rows(recruiter_dimensions, True, 10),
            "job_conditions_to_confirm": _priority_rows(candidate_dimensions, 12),
            "questions_for_employer": recommendations.get("job_confirmation_questions", []),
            "resume_actions": recommendations.get("resume_actions", []),
            "interview_preparation": recommendations.get("interview_questions", []),
            "development_plan": recommendations.get("development_plan", {}),
            "do_not_overclaim": "只写真实做过且能说明本人贡献的内容；学习中、协作参与和独立负责要明确区分。",
        })
    elif persona == "interviewer":
        base.update({
            "decision_scope": "用于统一提问与记录证据，不在面试现场自动给出录用结论。",
            "opening_checks": result.get("gates", []),
            "evidence_probes": recommendations.get("interview_questions", []),
            "follow_up_conditions": [item.get("follow_up_if") for item in recommendations.get("interview_questions", []) if item.get("follow_up_if")],
            "scorecard_dimensions": _priority_rows(recruiter_dimensions, 12),
            "strong_evidence_to_validate": _metric_rows(recruiter_dimensions, True, 8),
            "recording_areas": ["候选人事实原话", "本人行动", "结果与口径", "核验材料", "评分与理由", "待补事项"],
            "recording_rule": "把候选人的原话事实、追问结果和评分理由分开记录；未回答记为待补，不直接记为不具备。",
            "prohibited_topics": ["性别、婚育、民族、宗教、年龄等与岗位无关的受保护信息", "要求透露前雇主保密信息", "与岗位无关的健康或家庭隐私"],
        })
    else:
        base.update({
            "decision_scope": "用于发展对话、培养安排和内部机会评估，不单独决定晋升、调薪、调岗或解雇。",
            "target_role_readiness": analytics.get("score_balance", {}),
            "capability_matrix": _metric_rows(recruiter_dimensions, True, 20),
            "demonstrated_strengths": _metric_rows(recruiter_dimensions, True, 10),
            "capability_gaps": recommendations.get("verified_gaps", []),
            "evidence_needed": recommendations.get("evidence_needed", []),
            "development_priorities": _priority_rows(recruiter_dimensions + candidate_dimensions, 12),
            "development_plan": recommendations.get("development_plan", {}),
            "internal_mobility_constraints": _priority_rows(candidate_dimensions, 8),
            "success_evidence": recommendations.get("development_plan", {}).get("success_evidence", []),
        })
    return base


def _markdown_text(value: Any, default: str = "") -> str:
    """把不可信动态值转成单行Markdown纯文本，阻断标签、链接和图片语法注入。"""
    raw = default if value is None else str(value)
    normalized = re.sub(r"\s*\n\s*", " ", raw.replace("\r\n", "\n").replace("\r", "\n")).strip()
    escaped_html = html.escape(normalized, quote=False)
    escaped_markdown = re.sub(r"([\\`*_\[\]|!+\-])", r"\\\1", escaped_html)
    if escaped_markdown.startswith("="):
        return "&#61;" + escaped_markdown[1:]
    if escaped_markdown.startswith("@"):
        return "&#64;" + escaped_markdown[1:]
    return escaped_markdown


def _markdown_block_text(value: Any, default: str = "") -> str:
    """清洗独立段落，并转义可能在行首形成标题或列表的标记。"""
    text = _markdown_text(value, default)
    return re.sub(r"^(\s*)(#{1,6}|[-+]|\d+[.)])(?=\s)", r"\1\\\2", text)


def _markdown_list(items: Iterable[Any], empty: str = "- 暂无。") -> str:
    """把动态列表统一渲染为不能另起标签、标题或嵌套列表的Markdown项目。"""
    values = list(items)
    return "\n".join(f"- {_markdown_text(item, '待补')}" for item in values) if values else empty


def _markdown_json_block(value: Any) -> str:
    """使用缩进代码块展示JSON，避免数据中的围栏符号提前结束代码块。"""
    serialized = html.escape(json.dumps(value, ensure_ascii=False, indent=2), quote=False)
    return "\n".join(f"    {line}" for line in serialized.splitlines())


def _markdown_table(headers: List[str], rows: List[List[Any]]) -> str:
    """生成所有动态单元格均经过统一纯文本转义的Markdown表格。"""
    if not rows:
        return "暂无可展示的数据。"

    def clean(value: Any) -> str:
        return _markdown_text(value, "待补")

    return "\n".join([
        "| " + " | ".join(map(clean, headers)) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *["| " + " | ".join(map(clean, row)) + " |" for row in rows],
    ])


def _format_score(value: Any) -> str:
    return "待补资料" if value is None else f"{float(value):.2f}"


def _common_score_table(result: Dict[str, Any], first_side: str) -> str:
    scores = result.get("scores", {})
    confidence = result.get("confidence", {})
    order = ["overall", first_side, "candidate" if first_side == "recruiter" else "recruiter"]
    labels = {"overall": "综合匹配", "recruiter": "企业侧适配", "candidate": "求职者侧适配"}
    rows = []
    for key in order:
        formal = scores.get(key)
        displayed = _score_value(scores, key)
        note = "正式分" if formal is not None else "信息不足，补充资料后重算"
        rows.append([labels[key], _format_score(displayed) if displayed is not None else "暂不可比较", note])
    rows.append(["结果置信度", _format_score(confidence.get("score")), confidence.get("level", "")])
    rows.append(["处理状态", scores.get("status", ""), "仅ready_for_review可进入正式比较"])
    return _markdown_table(["项目", "结果", "说明"], rows)


def _category_table(result: Dict[str, Any], side: str) -> str:
    rows = result.get("analytics", {}).get("category_scores", {}).get(side, [])
    return _markdown_table(
        ["类别", "展示得分", "已知/总数", "数据状态", "系数占比"],
        [[
            row.get("category"),
            row.get("display_score") if row.get("display_score") is not None else "--",
            f'{row.get("known_count")}/{row.get("metric_count")}',
            row.get("status"),
            f'{row.get("coefficient_share", 0):.2f}%'
        ] for row in rows],
    )


def _gates_table(result: Dict[str, Any]) -> str:
    return _markdown_table(
        ["硬条件", "状态", "候选人信息", "岗位要求"],
        [[row.get("gate"), row.get("status"), row.get("candidate"), row.get("required")] for row in result.get("gates", [])],
    )


def _metrics_table(items: Iterable[Dict[str, Any]], priority: bool = False) -> str:
    selected = _priority_rows(items) if priority else _metric_rows(items, True)
    return _markdown_table(
        ["指标", "得分", "系数", "状态", "证据来源"],
        [[row.get("name"), row.get("score"), row.get("coefficient"), row.get("status"), "；".join(ref.get("field_path", "") for ref in row.get("evidence_refs", [])[:3]) or "待补"] for row in selected],
    )


def _question_markdown(questions: Iterable[Dict[str, Any]]) -> str:
    """生成经过统一转义的结构化问题，输入标签和Markdown语法只按文字显示。"""
    values = list(questions)
    if not values:
        return "- 暂无；建议围绕岗位核心职责准备真实案例。"
    blocks = []
    for index, item in enumerate(values, 1):
        blocks.append(
            f'{index}. **{_markdown_text(item.get("focus"), "核验项")}**：{_markdown_text(item.get("question"))}\n'
            f'   - 评分锚点：{_markdown_text(item.get("score_anchor"))}\n'
            f'   - 建议材料：{_markdown_text(item.get("evidence_to_request"))}\n'
            f'   - 追问条件：{_markdown_text(item.get("follow_up_if"), "回答边界或证据不清时继续追问。")}'
        )
    return "\n".join(blocks)


def _chart_markdown(charts: List[Dict[str, str]], report_path: Path | None) -> str:
    """只生成转义后的本地图表引用，图名和路径不能扩展为额外Markdown节点。"""
    lines = []
    for chart in charts:
        target = Path(chart["path"])
        if report_path:
            try:
                target_text = target.relative_to(report_path.parent).as_posix()
            except ValueError:
                target_text = target.as_posix()
        else:
            target_text = target.as_posix()
        safe_alt = _markdown_text(chart.get("alt"), "分析图")
        safe_target = quote(target_text, safe="/._~-")
        lines.append(f'![{safe_alt}]({safe_target})')
    return "\n\n".join(lines)


def render_markdown(result: Dict[str, Any], persona: str, charts: List[Dict[str, str]] | None = None, report_path: Path | None = None) -> str:
    """生成便于GitHub、飞书、钉钉、企业微信和通用代理展示的Markdown报告。"""
    persona = validate_persona(persona)
    charts = charts or []
    profile = ROLE_PROFILE[persona]
    payload = build_persona_payload(result, persona)
    recommendations = result.get("recommendations", {})
    analytics = result.get("analytics", {})
    meta = result.get("meta", {})
    sections = [
        f'# {profile["title"]}',
        f'> 候选人ID：{_markdown_text(meta.get("candidate_id"), "待补")}；岗位ID：{_markdown_text(meta.get("job_id"), "待补")}。{_markdown_text(payload["decision_scope"])}',
        "## 先看结论",
        _common_score_table(result, profile["side"]),
        _markdown_block_text(result.get("executive_summary")),
    ]

    if persona == "hr":
        sections.extend([
            "## 硬条件核验", _gates_table(result),
            "## 企业侧适配分类", _category_table(result, "recruiter"),
            "## 已有优势证据", _metrics_table(result.get("recruiter_dimensions", [])),
            "## 优先补证与追问", _metrics_table(result.get("recruiter_dimensions", []), True),
            "## 结构化面试问题", _question_markdown(recommendations.get("interview_questions", [])),
            "## 候选人侧约束", _metrics_table(result.get("candidate_dimensions", []), True),
            "## HR操作建议", _markdown_list(recommendations.get("recruiter_actions", [])),
        ])
    elif persona == "candidate":
        sections.extend([
            "## 岗位对你的适配分类", _category_table(result, "candidate"),
            "## 你已经展现的岗位能力", _metrics_table(result.get("recruiter_dimensions", [])),
            "## 建议先向企业确认的条件", _metrics_table(result.get("candidate_dimensions", []), True),
            "## 简历改进", _markdown_list(recommendations.get("resume_actions", [])),
            "## 向企业确认的问题", _question_markdown(recommendations.get("job_confirmation_questions", [])),
            "## 能力面试准备", _question_markdown(recommendations.get("interview_questions", [])),
            "## 30/60/90天提升建议", _markdown_json_block(recommendations.get("development_plan", {})),
            "## 真实陈述提醒", _markdown_block_text(payload.get("do_not_overclaim")),
        ])
    elif persona == "interviewer":
        sections.extend([
            "## 面试流程", "1. 核对岗位与硬条件；2. 使用统一核心问题；3. 按触发条件追问；4. 当场记录事实与证据；5. 面试后独立评分并复核。",
            "## 开场先核实的硬条件", _gates_table(result),
            "## 本场重点核验维度", _metrics_table(result.get("recruiter_dimensions", []), True),
            "## 结构化提问与评分锚点", _question_markdown(recommendations.get("interview_questions", [])),
            "## 追问条件", _markdown_list(payload.get("follow_up_conditions", []), "- 暂无预设追问。"),
            "## 面试记录区", _markdown_table(["核验维度", "事实原话", "本人行动", "结果/口径", "材料", "评分理由"], [[row.get("name"), "", "", "", "", ""] for row in payload.get("scorecard_dimensions", [])]),
            "## 已有强证据也要复核", _metrics_table(result.get("recruiter_dimensions", [])),
            "## 证据复核", "- 区分候选人个人贡献与团队结果；核对时间、指标口径、产物归属和保密边界。",
            "## 记录规则", _markdown_block_text(payload.get("recording_rule")),
            "## 不应询问的内容", _markdown_list(payload.get("prohibited_topics", [])),
        ])
    else:
        sections.extend([
            "## 目标岗位准备度", _common_score_table(result, "recruiter"),
            "## 能力矩阵", _metrics_table(payload.get("capability_matrix", [])),
            "## 已展现的能力", _metrics_table(result.get("recruiter_dimensions", [])),
            "## 已知能力差距", _metrics_table(recommendations.get("verified_gaps", []), True),
            "## 证据缺口", _metrics_table(recommendations.get("evidence_needed", []), True),
            "## 30/60/90天发展计划", _markdown_json_block(recommendations.get("development_plan", {})),
            "## 内部流动前需确认", _metrics_table(result.get("candidate_dimensions", []), True),
            "## 成果验收依据", _markdown_list(payload.get("success_evidence", [])),
        ])

    completeness = analytics.get("data_completeness", {})
    sections.extend([
        "## 数据质量与适用边界",
        f'- 已知指标：{_markdown_text(completeness.get("known_metrics", 0))}；待补指标：{_markdown_text(completeness.get("unknown_metrics", 0))}；不适用指标：{_markdown_text(completeness.get("not_applicable_metrics", 0))}。',
        "- 待补不等于不满足；正式结果仍需人工复核并允许当事人更正资料。",
    ])
    if charts:
        sections.extend(["## 图表", _chart_markdown(charts, report_path)])
    sections.extend([
        "## 方法与审计信息",
        f'- 有效指标：{_markdown_text(result.get("method", {}).get("indicator_count", 0))}项，系数来自可编辑Excel。',
        f'- Excel SHA-256：{_markdown_text(result.get("method", {}).get("indicator_workbook_sha256"), "待补")}。',
        "- 分数保留小数点后2位；只有资料充分且置信度达标时才给出正式综合分。",
    ])
    return "\n\n".join(str(section) for section in sections if section not in (None, "")) + "\n"


def render_html(result: Dict[str, Any], persona: str, charts: List[Dict[str, str]], report_path: Path | None = None) -> str:
    """生成四种真正分工不同、且不依赖外部网络资源的角色化HTML报告。"""
    persona = validate_persona(persona)
    profile = ROLE_PROFILE[persona]
    scores = result.get("scores", {})
    recommendations = result.get("recommendations", {})
    payload = build_persona_payload(result, persona)

    def table(headers: List[str], rows: List[List[Any]]) -> str:
        head = "".join(f"<th>{html.escape(str(item))}</th>" for item in headers)
        body_rows = rows or [["暂无", *([""] * (len(headers) - 1))]]
        body = "".join("<tr>" + "".join(f"<td>{html.escape(str(value if value is not None else '待补'))}</td>" for value in row) + "</tr>" for row in body_rows)
        return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    def metric_table(items: Iterable[Dict[str, Any]], priority: bool = False, limit: int = 10) -> str:
        selected = _priority_rows(items, limit) if priority else _metric_rows(items, True, limit)
        return table(["指标", "得分", "系数", "状态"], [[row.get("name"), row.get("score"), row.get("coefficient"), row.get("status")] for row in selected])

    def question_list(items: Iterable[Dict[str, Any]], recording: bool = False) -> str:
        rows = []
        for index, item in enumerate(list(items)[:14], 1):
            record = '<div class="record">事实记录：<span></span>　评分与理由：<span></span></div>' if recording else ""
            rows.append(
                f'<li><b>{index}. {html.escape(str(item.get("focus", "核验项")))}</b><p>{html.escape(str(item.get("question", "")))}</p>'
                f'<small>评分锚点：{html.escape(str(item.get("score_anchor", "")))}</small><br>'
                f'<small>追问条件：{html.escape(str(item.get("follow_up_if", "边界或证据不清时继续追问。")))}</small>{record}</li>'
            )
        return "<ol class=questions>" + "".join(rows or ["<li>暂无预设问题。</li>"]) + "</ol>"

    def bullet_list(items: Iterable[Any]) -> str:
        values = list(items)
        return "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in values) + "</ul>" if values else "<p>暂无。</p>"

    cards = []
    for label, key in (("综合匹配", "overall"), ("企业侧适配", "recruiter"), ("求职者侧适配", "candidate")):
        value = scores.get(key)
        cards.append(f'<article class="score"><span>{label}</span><strong>{_format_score(value) if value is not None else "暂不可比较"}</strong><small>{"正式分" if value is not None else "资料不足，补充后重算"}</small></article>')
    confidence = result.get("confidence", {}).get("score")
    cards.append(f'<article class="score"><span>结果置信度</span><strong>{_format_score(confidence)}</strong><small>{html.escape(str(scores.get("status", "")))}</small></article>')

    chart_cards = []
    for chart in charts:
        target = Path(chart["path"])
        if report_path:
            try:
                src = target.relative_to(report_path.parent).as_posix()
            except ValueError:
                src = target.as_uri()
        else:
            src = target.as_posix()
        chart_cards.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(chart["alt"])}"><figcaption>{html.escape(chart["title"])}</figcaption></figure>')

    recruiter = result.get("recruiter_dimensions", [])
    candidate = result.get("candidate_dimensions", [])
    gates = table(["硬条件", "状态", "最低要求", "核验信息"], [[row.get("gate"), row.get("status"), row.get("required", row.get("minimum_match_count")), row.get("evidence", row.get("evidence_rank"))] for row in result.get("gates", [])])
    sections = [f'<section><h2>执行摘要</h2><p>{html.escape(str(result.get("executive_summary", "")))}</p></section>']
    if persona == "hr":
        sections.extend([
            f'<section><h2>候选人分流与人工复核</h2>{gates}</section>',
            f'<section><h2>已核验的能力证据</h2>{metric_table(recruiter)}</section>',
            f'<section><h2>优先补证与风险</h2>{metric_table(recruiter, True, 12)}</section>',
            f'<section><h2>统一面试问题</h2>{question_list(recommendations.get("interview_questions", []))}</section>',
            f'<section><h2>候选人侧约束</h2>{metric_table(candidate, True, 10)}</section>',
            f'<section><h2>HR下一步</h2>{bullet_list(recommendations.get("recruiter_actions", []))}</section>',
        ])
    elif persona == "candidate":
        sections.extend([
            f'<section><h2>这份岗位对你的适配情况</h2>{metric_table(candidate, True, 12)}</section>',
            f'<section><h2>你已经展现的能力</h2>{metric_table(recruiter)}</section>',
            f'<section><h2>向企业确认的问题</h2>{question_list(recommendations.get("job_confirmation_questions", []))}</section>',
            f'<section><h2>简历改进</h2>{bullet_list(recommendations.get("resume_actions", []))}</section>',
            f'<section><h2>能力面试准备</h2>{question_list(recommendations.get("interview_questions", []))}</section>',
            f'<section><h2>30/60/90天提升建议</h2><pre>{html.escape(json.dumps(recommendations.get("development_plan", {}), ensure_ascii=False, indent=2))}</pre></section>',
        ])
    elif persona == "interviewer":
        scorecard = table(["核验维度", "事实原话", "本人行动", "结果与口径", "材料", "评分理由"], [[row.get("name"), "", "", "", "", ""] for row in payload.get("scorecard_dimensions", [])])
        sections.extend([
            '<section><h2>面试流程</h2><ol><li>核对岗位与硬条件</li><li>逐项询问统一核心问题</li><li>仅在触发条件出现时追问</li><li>记录事实与证据，不先下结论</li><li>面试后独立评分并复核</li></ol></section>',
            f'<section><h2>开场核验</h2>{gates}</section>',
            f'<section><h2>问题、评分锚点与追问条件</h2>{question_list(recommendations.get("interview_questions", []), True)}</section>',
            f'<section><h2>面试记录区</h2>{scorecard}</section>',
            f'<section><h2>证据复核</h2>{metric_table(payload.get("strong_evidence_to_validate", []))}<p>区分个人贡献与团队结果，核对时间、指标口径、产物归属和保密边界。</p></section>',
            f'<section><h2>禁止话题</h2>{bullet_list(payload.get("prohibited_topics", []))}</section>',
        ])
    else:
        sections.extend([
            f'<section><h2>目标岗位准备度</h2><p>当前状态：<b>{html.escape(str(payload.get("headline", {}).get("comparability", "暂不可比较")))}</b></p>{metric_table(recruiter, True, 12)}</section>',
            f'<section><h2>能力矩阵</h2>{metric_table(payload.get("capability_matrix", []), False, 20)}</section>',
            f'<section><h2>已展现优势</h2>{metric_table(payload.get("demonstrated_strengths", []))}</section>',
            f'<section><h2>已知能力差距</h2>{metric_table(recommendations.get("verified_gaps", []), True)}</section>',
            f'<section><h2>证据缺口</h2>{metric_table(recommendations.get("evidence_needed", []), True, 12)}</section>',
            f'<section><h2>内部流动约束</h2>{metric_table(candidate, True, 10)}</section>',
            f'<section><h2>30/60/90天发展计划</h2><pre>{html.escape(json.dumps(recommendations.get("development_plan", {}), ensure_ascii=False, indent=2))}</pre></section>',
            f'<section><h2>验收标准</h2>{bullet_list(payload.get("success_evidence", []))}</section>',
        ])

    sections.append(f'<section><h2>图表与数据质量</h2><div class="charts">{"".join(chart_cards)}</div></section>')
    accent = profile["accent"]
    css = '''body{margin:0;background:#F4F7FA;color:#172B4D;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}main{max-width:1120px;margin:32px auto;padding:0 22px}header{background:__ACCENT__;color:white;padding:30px;border-radius:16px}header h1{margin:0 0 6px}section{background:white;margin:18px 0;padding:22px 26px;border-radius:14px;box-shadow:0 4px 18px #1f29370d}h2{color:__ACCENT__;border-bottom:2px solid #E5E7EB;padding-bottom:8px}.score-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}.score{background:white;border-top:5px solid __ACCENT__;padding:16px;border-radius:12px}.score span,.score small{display:block;color:#64748B}.score strong{display:block;font-size:22px;color:__ACCENT__}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th{background:#243B53;color:white;text-align:left}th,td{padding:10px;border:1px solid #D9E2EC}tbody tr:nth-child(even){background:#F8FAFC}.questions li{margin-bottom:18px}.questions p{margin:5px 0}.record{margin-top:8px;padding:9px;background:#F8FAFC;border:1px dashed #94A3B8}.record span{display:inline-block;min-width:170px;border-bottom:1px solid #64748B}.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:18px}figure{margin:0;background:white;padding:14px;border-radius:14px}img{width:100%;height:auto}figcaption{font-weight:700;padding:8px}.notice{border-left:5px solid #D8A23A;background:#FFF7E6;padding:14px}pre{white-space:pre-wrap}@media(max-width:760px){.score-grid{grid-template-columns:repeat(2,1fr)}.charts{grid-template-columns:1fr}}'''.replace("__ACCENT__", accent)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(profile["title"])}</title><style>{css}</style></head><body><main>
<header><h1>{html.escape(profile["title"])}</h1><p>{html.escape(profile["subtitle"])}</p></header><div class="score-grid">{''.join(cards)}</div>
{''.join(sections)}
<section class="notice"><strong>适用边界：</strong>资料不足时显示“暂不可比较”；待补不等于不满足；受保护信息不参与评分；结果必须经过人工复核。</section>
</main></body></html>'''


def write_persona_report(result: Dict[str, Any], persona: str, output: str | Path, output_format: str = "auto", charts_dir: str | Path | None = None) -> Dict[str, Any]:
    """把指定角色报告写入JSON、Markdown、HTML或纯文本文件。"""
    persona = validate_persona(persona)
    path = Path(output)
    format_name = output_format.casefold()
    if format_name == "auto":
        format_name = {".md": "markdown", ".html": "html", ".htm": "html", ".json": "json", ".txt": "text"}.get(path.suffix.casefold(), "markdown")
    asset_dir = Path(charts_dir) if charts_dir else path.parent / f"{path.stem}_assets"
    charts = generate_report_charts(result, asset_dir, persona)
    if format_name == "json":
        content = json.dumps({"persona": build_persona_payload(result, persona), "charts": charts}, ensure_ascii=False, indent=2)
    elif format_name == "html":
        content = render_html(result, persona, charts, path)
    else:
        content = render_markdown(result, persona, charts, path)
        if format_name == "text":
            content = re.sub(r"[#>*`|]", "", content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"output": str(path), "format": format_name, "charts": charts, "persona": persona}
