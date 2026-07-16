"""本模块从同一匹配结果生成五张可离线使用的SVG分析图。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


COLORS = {
    "navy": "#243B53",
    "blue": "#3C78A8",
    "red": "#9B2438",
    "gold": "#D8A23A",
    "green": "#2E7D63",
    "orange": "#D96C2F",
    "gray": "#64748B",
    "light": "#EEF3F7",
    "ink": "#172B4D",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _svg_frame(title: str, subtitle: str, body: str, width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{_escape(title)}</title><desc id="desc">{_escape(subtitle)}</desc>
<rect width="100%" height="100%" fill="#FFFFFF" rx="16"/>
<rect x="0" y="0" width="10" height="{height}" fill="{COLORS['red']}" rx="5"/>
<text x="38" y="42" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="22" font-weight="700" fill="{COLORS['ink']}">{_escape(title)}</text>
<text x="38" y="68" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="12" fill="{COLORS['gray']}">{_escape(subtitle)}</text>
{body}</svg>'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _number(value: Any, fallback: float = 0.0) -> float:
    """把可空分数转换为图表数值，避免资料不足时报错。"""
    try:
        return fallback if value is None else float(value)
    except (TypeError, ValueError):
        return fallback


def _horizontal_bars(title: str, subtitle: str, values: Sequence[Tuple[str, Any, str]], path: Path, color: str = "blue") -> None:
    width = 980
    row_height = 46
    height = 100 + max(1, len(values)) * row_height + 30
    label_x, bar_x, bar_width = 38, 330, 560
    parts = []
    for index, (label, raw, note) in enumerate(values):
        known = raw is not None
        score = max(0.0, min(100.0, _number(raw)))
        y = 104 + index * row_height
        parts.append(f'<text x="{label_x}" y="{y + 16}" font-family="Microsoft YaHei, sans-serif" font-size="13" fill="{COLORS["ink"]}">{_escape(label[:28])}</text>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="20" rx="10" fill="{COLORS["light"]}"/>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width * score / 100:.1f}" height="20" rx="10" fill="{COLORS[color]}"/>')
        display = f"{score:.2f}" if known else "--"
        parts.append(f'<text x="{bar_x + bar_width + 14}" y="{y + 15}" font-family="Consolas, sans-serif" font-size="13" font-weight="700" fill="{COLORS["ink"]}">{display}</text>')
        if note:
            parts.append(f'<text x="{bar_x}" y="{y + 36}" font-family="Microsoft YaHei, sans-serif" font-size="10" fill="{COLORS["gray"]}">{_escape(note[:72])}</text>')
    _write(path, _svg_frame(title, subtitle, "".join(parts), width, height))


def _stacked_bar(title: str, subtitle: str, segments: Sequence[Tuple[str, float, str]], path: Path) -> None:
    width, height = 980, 260
    total = sum(max(0.0, float(value)) for _, value, _ in segments) or 1.0
    x, y, bar_width = 40, 118, 880
    current_x = x
    parts = []
    for label, value, color in segments:
        segment_width = bar_width * max(0.0, float(value)) / total
        parts.append(f'<rect x="{current_x:.1f}" y="{y}" width="{segment_width:.1f}" height="38" fill="{COLORS[color]}"/>')
        if segment_width >= 74:
            parts.append(f'<text x="{current_x + segment_width / 2:.1f}" y="{y + 24}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">{_escape(label)} {value:.0f}</text>')
        current_x += segment_width
    legend_x = 40
    for label, value, color in segments:
        parts.append(f'<rect x="{legend_x}" y="188" width="14" height="14" rx="3" fill="{COLORS[color]}"/>')
        parts.append(f'<text x="{legend_x + 21}" y="200" font-family="Microsoft YaHei, sans-serif" font-size="12" fill="{COLORS["ink"]}">{_escape(label)}：{value:.0f}</text>')
        legend_x += 190
    _write(path, _svg_frame(title, subtitle, "".join(parts), width, height))


def generate_report_charts(result: Dict[str, Any], output_dir: str | Path, persona: str) -> List[Dict[str, str]]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = persona
    scores = result.get("scores", {})
    charts: List[Dict[str, str]] = []
    comparable = scores.get("status") == "ready_for_review"
    overall = scores.get("overall")
    recruiter = scores.get("recruiter")
    candidate = scores.get("candidate")

    overview = directory / f"{prefix}_01_score_overview.svg"
    _horizontal_bars(
        "双向匹配总览",
        "只有资料充分时显示正式分；资料不足的维度以“--”表示。",
        [
            ("综合匹配", overall, str(scores.get("band", "")) if comparable else "暂不可比较，补充资料后重算"),
            ("企业侧适配", recruiter, "候选人能力与岗位要求" if recruiter is not None else "资料不足"),
            ("求职者侧适配", candidate, "岗位条件与个人偏好" if candidate is not None else "资料不足"),
            ("结果置信度", _number(result.get("confidence", {}).get("score")), "取决于输入完整性与证据质量"),
        ],
        overview,
        "red" if persona == "hr" else "blue" if persona == "candidate" else "green" if persona == "talent_manager" else "gold",
    )
    charts.append({"id": "score_overview", "title": "双向匹配总览", "path": str(overview), "alt": "综合、企业侧、求职者侧与置信度横向条形图"})

    side = "recruiter" if persona in {"hr", "interviewer"} else "candidate"
    categories = result.get("analytics", {}).get("category_scores", {}).get(side, [])
    category_path = directory / f"{prefix}_02_category_profile.svg"
    _horizontal_bars(
        "岗位适配画像" if side == "recruiter" else "岗位体验画像",
        "仅展示有足够输入数据的类别；类别分数是该类别内有效指标的系数加权平均。",
        [(row["category"], row.get("display_score"), f'已知{row["known_count"]}/{row["metric_count"]}项') for row in categories][:10],
        category_path,
        "red" if persona == "hr" else "blue" if persona == "candidate" else "green" if persona == "talent_manager" else "gold",
    )
    charts.append({"id": "category_profile", "title": "类别画像", "path": str(category_path), "alt": "各匹配类别得分条形图"})

    driver_path = directory / f"{prefix}_03_top_drivers.svg"
    drivers = [item for item in result.get("analytics", {}).get("top_contribution_drivers", []) if item.get("score") is not None]
    _horizontal_bars(
        "主要得分驱动因素",
        "按归一权重后的贡献排序；高分不代表事实已被面试核验。",
        [(item.get("name") or item.get("id"), _number(item.get("score")), f'系数{item.get("coefficient", 0):.2f}｜贡献{item.get("contribution", 0):.2f}') for item in drivers[:8]],
        driver_path,
        "gold",
    )
    charts.append({"id": "top_drivers", "title": "主要得分驱动因素", "path": str(driver_path), "alt": "贡献最高指标条形图"})

    completeness = result.get("analytics", {}).get("data_completeness", {})
    completeness_path = directory / f"{prefix}_04_data_completeness.svg"
    _stacked_bar(
        "数据完整性",
        "unknown不会自动记为0，但会减少可用证据并降低结论可靠性。",
        [
            ("已知指标", _number(completeness.get("known_metrics")), "green"),
            ("待补充指标", _number(completeness.get("unknown_metrics")), "gray"),
            ("不适用指标", _number(completeness.get("not_applicable_metrics")), "gold"),
        ],
        completeness_path,
    )
    charts.append({"id": "data_completeness", "title": "数据完整性", "path": str(completeness_path), "alt": "已知指标与待补充指标比例图"})

    dimensions = result.get("recruiter_dimensions", []) if side == "recruiter" else result.get("candidate_dimensions", [])
    unknown = sorted(
        [item for item in dimensions if item.get("effective_score") is None and item.get("status") != "not_applicable"],
        key=lambda item: (-(item.get("coefficient") or 0), str(item.get("id"))),
    )
    priorities = sorted([item for item in dimensions if item.get("score") is not None], key=lambda item: (item["score"], -item.get("coefficient", 0)))
    priority_values = [
        (item.get("name") or item.get("id"), _number(item.get("coefficient")) * 10, f'待补资料｜系数{item.get("coefficient", 0):.2f}')
        for item in unknown[:4]
    ] + [
        (item.get("name") or item.get("id"), _number(item.get("score")), f'已评分｜系数{item.get("coefficient", 0):.2f}')
        for item in priorities[:4]
    ]
    priority_path = directory / f"{prefix}_05_priority_review.svg"
    _horizontal_bars(
        "优先核验与改进项" if persona == "hr" else "优先确认与提升项",
        "待补项按系数×10展示优先级，已评分项展示实际分；两类数值含义不同。",
        priority_values,
        priority_path,
        "orange",
    )
    charts.append({"id": "priority_review", "title": "优先核验与改进项", "path": str(priority_path), "alt": "低分优先核验指标条形图"})
    return charts
