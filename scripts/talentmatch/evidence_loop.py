"""本模块实现“解析确认—补充证据—重新匹配—前后对比”的可复核闭环。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from .engine import match_pair
from .parser import parse_candidate, parse_job
from .privacy import redact_object


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _changed_field_paths(value: Any, prefix: str = "") -> list[str]:
    """列出补证对象涉及的字段路径，不在审计摘要中重复输出原始值。"""
    if isinstance(value, dict):
        paths = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            nested = _changed_field_paths(child, path)
            paths.extend(nested or [path])
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            nested = _changed_field_paths(child, path)
            paths.extend(nested or [path])
        return paths
    return [prefix] if prefix else []


def _unknown_priorities(result: Dict[str, Any], limit: int = 12) -> list[Dict[str, Any]]:
    dimensions = result.get("recruiter_dimensions", []) + result.get("candidate_dimensions", [])
    unknown = [row for row in dimensions if row.get("effective_score") is None and row.get("status") != "not_applicable"]
    unknown.sort(key=lambda row: (-(row.get("coefficient") or 0), str(row.get("id"))))
    return [{
        "id": row.get("id"),
        "name": row.get("name"),
        "side": row.get("side"),
        "coefficient": row.get("coefficient"),
        "candidate_field_paths": row.get("candidate_field_paths", []),
        "job_field_paths": row.get("job_field_paths", []),
    } for row in unknown[:limit]]


def prepare_evidence_review(candidate_input: Any, job_input: Any, metrics_path: str | None = None, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """先返回保守解析结果和待确认问题，让使用者确认后再把分数用于比较。"""
    candidate = parse_candidate(candidate_input)
    job = parse_job(job_input)
    result = match_pair(candidate, job, metrics_path=metrics_path, config=config)
    return {
        "stage": "awaiting_confirmation",
        "confirmation_required": True,
        "parsed_candidate": redact_object(candidate),
        "parsed_job": redact_object(job),
        "high_weight_unknowns": _unknown_priorities(result),
        "questions_for_candidate": result.get("recommendations", {}).get("interview_questions", []),
        "questions_for_employer": result.get("recommendations", {}).get("job_confirmation_questions", []),
        "current_status": result.get("scores", {}).get("status"),
        "current_public_scores": {key: result.get("scores", {}).get(key) for key in ("overall", "recruiter", "candidate")},
    }


def reassess_with_evidence(
    candidate_input: Any,
    job_input: Any,
    evidence_update: Dict[str, Any],
    metrics_path: str | None = None,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """合并经确认的新证据并重算，完整保留修改前后状态与指标变化。"""
    if not isinstance(evidence_update, dict):
        raise ValueError("evidence_update必须是JSON对象")
    candidate = parse_candidate(candidate_input)
    job = parse_job(job_input)
    before = match_pair(candidate, job, metrics_path=metrics_path, config=config)
    updated_candidate = _deep_merge(candidate, evidence_update.get("candidate", {}))
    updated_job = _deep_merge(job, evidence_update.get("job", {}))
    after = match_pair(updated_candidate, updated_job, metrics_path=metrics_path, config=config)

    before_dimensions = {row["id"]: row for row in before.get("recruiter_dimensions", []) + before.get("candidate_dimensions", [])}
    after_dimensions = {row["id"]: row for row in after.get("recruiter_dimensions", []) + after.get("candidate_dimensions", [])}
    changes = []
    for indicator_id in sorted(set(before_dimensions) | set(after_dimensions)):
        old, new = before_dimensions.get(indicator_id, {}), after_dimensions.get(indicator_id, {})
        if old.get("score") != new.get("score") or old.get("status") != new.get("status"):
            changes.append({
                "id": indicator_id,
                "name": new.get("name") or old.get("name"),
                "before_score": old.get("score"),
                "after_score": new.get("score"),
                "before_status": old.get("status"),
                "after_status": new.get("status"),
            })
    return {
        "stage": "reassessed",
        "applied_update": {
            "changed_fields": sorted(set(_changed_field_paths(evidence_update))),
            "redacted_preview": redact_object(evidence_update),
        },
        "before": before,
        "after": after,
        "comparison": {
            "before_status": before.get("scores", {}).get("status"),
            "after_status": after.get("scores", {}).get("status"),
            "before_public_score": before.get("scores", {}).get("overall"),
            "after_public_score": after.get("scores", {}).get("overall"),
            "before_known_metrics": before.get("analytics", {}).get("data_completeness", {}).get("known_metrics"),
            "after_known_metrics": after.get("analytics", {}).get("data_completeness", {}).get("known_metrics"),
            "changed_indicators": changes,
        },
    }
