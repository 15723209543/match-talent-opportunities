"""本模块依据资料完整度、证据覆盖率和可评分指标比例计算结果置信度。"""

from __future__ import annotations

from typing import Any, Dict, List

from .model import clamp, safe_float


def _completeness(record: Dict[str, Any], fields: List[str]) -> float:
    """计算关键字段中实际提供内容的比例。"""
    present = sum(record.get(field) not in (None, "", [], {}) for field in fields)
    return present / len(fields) if fields else 0.0


def calculate_confidence(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    evidence_matrix: List[Dict[str, Any]],
    warnings: List[str],
    data_sufficiency: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """返回0—100置信度；没有证据行时证据覆盖率为0，不以中性值代替。"""
    candidate_completeness = _completeness(
        candidate,
        ["target_roles", "skills", "experience_years", "education", "preferred_locations", "salary_expectation", "growth_goals"],
    )
    job_completeness = _completeness(
        job,
        ["title", "required_skills", "responsibilities", "min_experience_years", "location", "salary_range", "growth_offerings"],
    )
    evidence_rows = [row for row in evidence_matrix if row.get("type") in {"required_skill", "preferred_skill"}]
    evidence_coverage = (
        sum(row.get("evidence") not in {None, "", "not_provided"} for row in evidence_rows) / len(evidence_rows)
        if evidence_rows else 0.0
    )
    candidate_certainty = safe_float(candidate.get("parser", {}).get("certainty"), 0.5)
    job_certainty = safe_float(job.get("parser", {}).get("certainty"), 0.5)
    parser_certainty = min(
        clamp(0.5 if candidate_certainty is None else candidate_certainty),
        clamp(0.5 if job_certainty is None else job_certainty),
    )

    sufficiency = data_sufficiency or {}
    side_rates = [
        safe_float(sufficiency.get(side, {}).get("known_weight_rate"), 0.0) or 0.0
        for side in ("recruiter", "candidate")
    ]
    metric_coverage = min(side_rates) / 100 if side_rates else 0.0
    warning_penalty = min(0.25, len(warnings) * 0.025)
    score = clamp(
        0.24 * candidate_completeness
        + 0.24 * job_completeness
        + 0.24 * evidence_coverage
        + 0.18 * metric_coverage
        + 0.10 * parser_certainty
        - warning_penalty
    )
    percent = round(score * 100, 2)
    return {
        "score": percent,
        "level": "high" if percent >= 80 else "medium" if percent >= 60 else "low",
        "components": {
            "candidate_completeness": round(candidate_completeness * 100, 2),
            "job_completeness": round(job_completeness * 100, 2),
            "evidence_coverage": round(evidence_coverage * 100, 2),
            "metric_coverage": round(metric_coverage * 100, 2),
            "parser_certainty": round(parser_certainty * 100, 2),
            "warning_penalty": round(warning_penalty * 100, 2),
        },
        "interpretation": "置信度衡量现有资料能否支持比较，不等同于岗位匹配分。",
    }
