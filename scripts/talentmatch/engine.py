"""本模块负责从输入解析到双向评分、审计、建议和分析汇总的完整匹配流程。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .analytics import build_analytics
from .confidence import calculate_confidence
from .constants import MIN_COMPARABLE_CONFIDENCE
from .excel_config import DEFAULT_METRICS_WORKBOOK, load_metric_config
from .fairness import audit_record, sanitize_for_scoring
from .gates import evaluate_gates
from .parser import parse_candidate, parse_job
from .privacy import redact_object
from .recommendations import build_recommendations
from .scoring import score_all
from .metrics import resolve_as_of_date
from .text import harmonic
from .validation import validate_candidate, validate_job


HARD_FAILURE_CAP = 49.00


def load_weights(path: str | None = None, profile: str = "general") -> Dict[str, Any]:
    """保留旧名称；实际配置完全来自Excel。"""
    return load_metric_config(path, profile)


def _band(score: float | None, status: str) -> str:
    if status in {"insufficient_data", "hard_requirement_unverified"}:
        return status
    if status == "hard_failure":
        return "hard_failure"
    if score is None:
        return "not_available"
    return "strong" if score >= 80 else "promising" if score >= 65 else "conditional" if score >= 50 else "weak"


def _summary(status: str, overall: float | None, confidence: Dict[str, Any], gates, matrix) -> str:
    failed = [gate["gate"] for gate in gates if gate.get("status") == "fail"]
    missing = [row["requirement"] for row in matrix if row.get("type") == "required_skill" and row.get("status") == "missing"]
    if status == "hard_failure":
        return "发现需要先人工核实的硬性条件不符：" + "、".join(failed[:3]) + "。该结果不能直接用于录用或淘汰。"
    if status == "hard_requirement_unverified":
        unknown = [gate["gate"] for gate in gates if gate.get("status") == "unknown"]
        return "尚有硬性条件无法核验，暂不形成正式匹配分或排名：" + "、".join(unknown[:3]) + "。请补充事实后重新计算。"
    if status == "insufficient_data":
        return "现有资料不足以形成可比较的正式匹配分。请先补齐关键经历、岗位要求、双向偏好和可核验事实。"
    if missing:
        return f"当前正式匹配分为{overall:.2f}，主要待核实项包括：" + "、".join(missing[:3]) + "。"
    return f"当前正式匹配分为{overall:.2f}；进入下一步前仍应通过结构化面试核验证据，并确认双方真实偏好。"


def match_pair(
    candidate_input: Any,
    job_input: Any,
    metrics_path: str | None = None,
    config: Dict[str, Any] | None = None,
    profile: str = "general",
    as_of_date: Any = None,
) -> Dict[str, Any]:
    """执行一次双向匹配；批处理可传入已加载配置，避免同一请求重复读取Excel。"""
    candidate_raw = parse_candidate(candidate_input)
    job_raw = parse_job(job_input)
    candidate_validation = validate_candidate(candidate_raw)
    job_validation = validate_job(job_raw)
    errors = candidate_validation["errors"] + job_validation["errors"]
    if errors:
        raise ValueError("输入校验失败：" + "；".join(errors))
    warnings = (
        candidate_validation["warnings"]
        + job_validation["warnings"]
        + list(candidate_raw.get("parser", {}).get("warnings", []))
        + list(job_raw.get("parser", {}).get("warnings", []))
    )

    # 原始对象仅用于审计；后续指标、硬条件和证据引用都使用净化副本。
    candidate_fairness = audit_record(candidate_raw)
    job_fairness = audit_record(job_raw)
    candidate = sanitize_for_scoring(candidate_raw)
    job = sanitize_for_scoring(job_raw)
    scoring_date = resolve_as_of_date(as_of_date)

    active_config = config or load_metric_config(metrics_path, profile)
    (
        recruiter_score,
        recruiter_dimensions,
        recruiter_state,
        candidate_score,
        candidate_dimensions,
        candidate_state,
        evidence_matrix,
    ) = score_all(candidate, job, active_config, scoring_date)
    data_sufficiency = {"recruiter": recruiter_state, "candidate": candidate_state}

    recruiter_estimate = recruiter_state.get("estimate")
    candidate_estimate = candidate_state.get("estimate")
    provisional_overall = None
    if recruiter_estimate is not None and candidate_estimate is not None:
        if recruiter_estimate == 0 or candidate_estimate == 0:
            provisional_overall = 0.0
        else:
            provisional_overall = round(harmonic(
                [recruiter_estimate, candidate_estimate],
                [active_config["overall"]["overall_recruiter"], active_config["overall"]["overall_candidate"]],
            ), 2)

    gates = evaluate_gates(candidate, job)
    failed_gates = [gate for gate in gates if gate.get("status") == "fail"]
    unknown_hard_gates = [gate for gate in gates if gate.get("status") == "unknown"]
    candidate_fairness["scoring_sanitization_applied"] = bool(
        candidate_fairness["protected_trait_flags"] or candidate_fairness["prompt_injection_flags"]
    )
    job_fairness["scoring_sanitization_applied"] = bool(
        job_fairness["protected_trait_flags"] or job_fairness["prompt_injection_flags"]
    )
    if candidate_fairness["protected_trait_flags"]:
        warnings.append("candidate_protected_attributes_excluded_from_scoring")
    if job_fairness["protected_trait_flags"]:
        warnings.append("job_contains_protected_trait_criteria_excluded_from_scoring")
    if candidate_fairness["prompt_injection_flags"] or job_fairness["prompt_injection_flags"]:
        warnings.append("embedded_instructions_ignored")
    warnings = sorted(set(warnings))

    confidence = calculate_confidence(candidate, job, evidence_matrix, warnings, data_sufficiency)
    sides_scorable = bool(recruiter_state["scorable"] and candidate_state["scorable"])
    if failed_gates:
        status = "hard_failure"
    elif unknown_hard_gates:
        status = "hard_requirement_unverified"
    elif not sides_scorable or confidence["score"] < MIN_COMPARABLE_CONFIDENCE:
        status = "insufficient_data"
    else:
        status = "ready_for_review"

    formal_overall = provisional_overall if status == "ready_for_review" else None
    cap_applied = False
    if status == "hard_failure" and provisional_overall is not None and provisional_overall > HARD_FAILURE_CAP:
        provisional_overall = HARD_FAILURE_CAP
        cap_applied = True

    result: Dict[str, Any] = {
        "meta": {
            "engine": "TalentLens",
            "engine_version": "4.2.0",
            "schema_version": "4.2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidate_id": candidate_raw.get("id", "candidate"),
            "job_id": job_raw.get("id", "job"),
        },
        "scoring_context": {
            "as_of_date": scoring_date.isoformat(),
            "protected_content_policy": "audit_raw_then_score_sanitized_copy",
            "source_mutated": False,
        },
        "scores": {
            "status": status,
            "overall": formal_overall,
            "provisional_overall": provisional_overall,
            "band": _band(formal_overall, status),
            "recruiter": recruiter_score,
            "candidate": candidate_score,
            "provisional_recruiter": recruiter_estimate,
            "provisional_candidate": candidate_estimate,
            "precision": 2,
            "hard_failure_cap_applied": cap_applied,
            "data_sufficiency": data_sufficiency,
        },
        "confidence": confidence,
        "executive_summary": _summary(status, formal_overall, confidence, gates, evidence_matrix),
        "gates": gates,
        "recruiter_dimensions": recruiter_dimensions,
        "candidate_dimensions": candidate_dimensions,
        "evidence_matrix": evidence_matrix,
        "warnings": warnings,
        "fairness_audit": {"candidate": candidate_fairness, "job": job_fairness},
        "method": {
            "formula": "weighted_harmonic_mean",
            "indicator_workbook": active_config["source"],
            "indicator_workbook_sha256": active_config["sha256"],
            "indicator_count": active_config["metric_count"],
            "weight_profile": active_config.get("profile", {"id": "general"}),
            "weight_profile_override_count": active_config.get("profile_override_count", 0),
            "overall_coefficients": active_config["overall"],
            "coefficient_policy": "single_match_reads_once; batch_reads_once_per_request; next_request_reloads",
            "default_indicator_workbook": str(DEFAULT_METRICS_WORKBOOK),
            "hard_failure_cap": HARD_FAILURE_CAP,
            "minimum_comparable_confidence": MIN_COMPARABLE_CONFIDENCE,
            "unknown_policy": "follow_each_excel_row_missing_policy_and_report_sufficiency",
            "protected_traits_used": False,
            "protected_content_flow": "raw_input_for_audit; sanitized_copy_for_metrics_gates_and_evidence",
            "as_of_date": scoring_date.isoformat(),
            "network_calls": False,
            "human_review_required": True,
        },
    }
    result["recommendations"] = build_recommendations(result)
    result["analytics"] = build_analytics(result)
    return redact_object(result)
