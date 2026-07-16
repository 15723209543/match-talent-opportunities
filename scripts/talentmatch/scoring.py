"""本模块依据Excel系数计算双侧分数、数据充分性、指标贡献和证据来源。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .constants import MIN_KNOWN_METRICS, MIN_KNOWN_WEIGHT_RATE
from .metrics import METRIC_FUNCTIONS, MetricContext, evaluate_metric
from .text import quantified_evidence


# 每项指标关联到候选人或岗位中的原始字段，报告可据此追溯判断来源。
METRIC_SOURCE_FIELDS: Dict[str, List[Tuple[str, str]]] = {
    "required_skill_coverage": [("candidate", "skills"), ("job", "required_skills")],
    "preferred_skill_coverage": [("candidate", "skills"), ("job", "preferred_skills")],
    "skill_proficiency": [("candidate", "skills"), ("job", "required_skills")],
    "skill_experience_years": [("candidate", "skills"), ("job", "required_skills")],
    "skill_recency": [("candidate", "skills"), ("job", "required_skills")],
    "evidence_strength": [("candidate", "skills"), ("candidate", "experiences")],
    "quantified_impact": [("candidate", "skills"), ("candidate", "experiences")],
    "responsibility_overlap": [("candidate", "summary"), ("candidate", "experiences"), ("job", "responsibilities")],
    "total_experience": [("candidate", "experience_years"), ("job", "min_experience_years")],
    "industry_experience": [("candidate", "industry_experience"), ("candidate", "industries"), ("job", "industries")],
    "seniority_alignment": [("candidate", "current_seniority"), ("job", "seniority")],
    "project_complexity": [("candidate", "project_complexity"), ("job", "project_complexity_required")],
    "education_fit": [("candidate", "education"), ("job", "education")],
    "certification_fit": [("candidate", "certifications"), ("job", "certifications")],
    "language_fit": [("candidate", "languages"), ("job", "languages")],
    "leadership_experience": [("candidate", "leadership_years"), ("job", "leadership_required_years")],
    "collaboration_evidence": [("candidate", "collaboration_evidence"), ("job", "collaboration_requirements")],
    "location_feasibility": [("candidate", "preferred_locations"), ("job", "location")],
    "work_mode_feasibility": [("candidate", "preferred_work_modes"), ("job", "work_modes")],
    "employment_type_feasibility": [("candidate", "employment_types"), ("job", "employment_type")],
    "availability_feasibility": [("candidate", "availability"), ("job", "availability_required")],
    "skill_breadth": [("candidate", "skills"), ("job", "required_skills"), ("job", "preferred_skills")],
    "core_skill_depth": [("candidate", "skills"), ("job", "required_skills")],
    "transferable_skill_readiness": [("candidate", "transferable_skills"), ("job", "transferable_skill_requirements")],
    "toolchain_compatibility": [("candidate", "toolchains"), ("job", "toolchains")],
    "domain_knowledge": [("candidate", "domain_knowledge"), ("job", "domain_knowledge")],
    "achievement_consistency": [("candidate", "experiences")],
    "evidence_recency": [("candidate", "skills"), ("candidate", "experiences")],
    "outcome_relevance": [("candidate", "experiences"), ("candidate", "skills"), ("job", "responsibilities")],
    "ownership_evidence": [("candidate", "ownership_evidence"), ("job", "ownership_expectations")],
    "problem_solving_evidence": [("candidate", "problem_solving_evidence"), ("job", "problem_solving_expectations")],
    "communication_evidence": [("candidate", "communication_evidence"), ("job", "communication_expectations")],
    "stakeholder_management": [("candidate", "stakeholder_evidence"), ("job", "stakeholder_expectations")],
    "delivery_reliability": [("candidate", "delivery_evidence"), ("job", "delivery_expectations")],
    "innovation_evidence": [("candidate", "innovation_evidence"), ("job", "innovation_expectations")],
    "risk_management_evidence": [("candidate", "risk_management_evidence"), ("job", "risk_management_expectations")],
    "learning_agility": [("candidate", "learning_evidence"), ("job", "learning_agility_expectations")],
    "adaptability_evidence": [("candidate", "adaptability_evidence"), ("job", "adaptability_expectations")],
    "decision_quality_evidence": [("candidate", "decision_evidence"), ("job", "decision_quality_expectations")],
    "analytical_thinking": [("candidate", "analytical_evidence"), ("job", "analytical_expectations")],
    "customer_orientation": [("candidate", "customer_evidence"), ("job", "customer_orientation_expectations")],
    "compliance_awareness": [("candidate", "compliance_evidence"), ("job", "compliance_expectations")],
    "target_role_alignment": [("candidate", "target_roles"), ("job", "title")],
    "growth_goal_alignment": [("candidate", "growth_goals"), ("job", "growth_offerings")],
    "learning_opportunity_alignment": [("candidate", "learning_goals"), ("job", "learning_offerings")],
    "compensation_alignment": [("candidate", "salary_expectation"), ("job", "salary_range")],
    "location_preference_alignment": [("candidate", "preferred_locations"), ("job", "location")],
    "work_mode_preference_alignment": [("candidate", "preferred_work_modes"), ("job", "work_modes")],
    "employment_type_preference": [("candidate", "employment_types"), ("job", "employment_type")],
    "start_date_alignment": [("candidate", "availability"), ("job", "availability_required")],
    "values_alignment": [("candidate", "values"), ("job", "values")],
    "industry_interest_alignment": [("candidate", "industry_interests"), ("job", "industries")],
    "seniority_preference_alignment": [("candidate", "desired_seniority"), ("job", "seniority")],
    "workload_preference_alignment": [("candidate", "preferred_workload"), ("job", "workload")],
    "travel_preference_alignment": [("candidate", "travel_preference"), ("job", "travel_requirement")],
    "team_culture_alignment": [("candidate", "team_culture_preferences"), ("job", "team_culture")],
    "role_stability_alignment": [("candidate", "role_stability_preference"), ("job", "role_stability")],
    "benefits_alignment": [("candidate", "benefit_preferences"), ("job", "benefits")],
    "manager_style_alignment": [("candidate", "manager_style_preferences"), ("job", "manager_style")],
    "career_path_alignment": [("candidate", "career_path_goals"), ("job", "career_paths")],
    "role_mission_alignment": [("candidate", "role_mission_preferences"), ("job", "role_mission")],
    "daily_task_interest": [("candidate", "daily_task_interests"), ("job", "daily_tasks")],
    "autonomy_preference_alignment": [("candidate", "autonomy_preference"), ("job", "autonomy_level")],
    "feedback_frequency_alignment": [("candidate", "feedback_frequency_preference"), ("job", "feedback_frequency")],
    "collaboration_style_alignment": [("candidate", "collaboration_style_preferences"), ("job", "collaboration_style")],
    "decision_style_alignment": [("candidate", "decision_style_preferences"), ("job", "decision_style")],
    "pace_preference_alignment": [("candidate", "pace_preference"), ("job", "pace")],
    "innovation_environment_alignment": [("candidate", "innovation_environment_preferences"), ("job", "innovation_environment")],
    "learning_budget_alignment": [("candidate", "learning_budget_expectation"), ("job", "learning_budget")],
    "mentorship_access_alignment": [("candidate", "mentorship_preferences"), ("job", "mentorship")],
    "promotion_clarity_alignment": [("candidate", "promotion_clarity_preference"), ("job", "promotion_clarity")],
    "compensation_structure_alignment": [("candidate", "compensation_structure_preferences"), ("job", "compensation_structure")],
    "bonus_expectation_alignment": [("candidate", "bonus_expectation"), ("job", "bonus_range")],
    "annual_leave_alignment": [("candidate", "min_annual_leave_days"), ("job", "annual_leave_days")],
    "schedule_flexibility_alignment": [("candidate", "schedule_flexibility_preferences"), ("job", "schedule_flexibility")],
    "commute_feasibility": [("candidate", "max_commute_minutes"), ("job", "commute_minutes")],
    "travel_burden_alignment": [("candidate", "max_travel_days_per_month"), ("job", "travel_days_per_month")],
    "job_security_alignment": [("candidate", "job_security_preference"), ("job", "job_security")],
    "purpose_alignment": [("candidate", "purpose_preferences"), ("job", "purpose")],
    "psychological_safety_alignment": [("candidate", "psychological_safety_preferences"), ("job", "psychological_safety")],
}


def _effective_score(raw: Any, missing_policy: str) -> Any:
    if raw is not None:
        return float(raw)
    policy = str(missing_policy or "exclude").strip().casefold()
    if policy == "neutral":
        return 0.5
    if policy == "zero":
        return 0.0
    return None


def _nonempty(value: Any) -> bool:
    """判断字段是否包含可引用内容。"""
    return value not in (None, "", [], {})


def _snippet(value: Any, limit: int = 180) -> str:
    """把结构化字段压缩成适合审计记录的短文本。"""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    text = " ".join(text.split())
    return text[:limit]


def _evidence_grade(source: str, value: Any) -> str:
    """按信息具体程度给来源标注A、B或C；等级不代表已经核验。"""
    if source == "job":
        return "C"
    text = _snippet(value)
    if quantified_evidence(text) >= 0.75:
        return "A"
    if len(text) >= 28 or isinstance(value, (dict, list)):
        return "B"
    return "C"


def _evidence_refs(indicator_id: str, context: MetricContext) -> List[Dict[str, Any]]:
    """为单项指标生成来源字段、片段和证据等级。"""
    refs: List[Dict[str, Any]] = []
    skill_metric = indicator_id in {
        "required_skill_coverage", "preferred_skill_coverage", "skill_proficiency",
        "skill_experience_years", "skill_recency", "evidence_strength",
        "quantified_impact", "skill_breadth", "core_skill_depth",
    }
    if skill_metric:
        for row in context.required_rows + context.preferred_rows:
            field_path = row.get("candidate_field_path")
            if not field_path:
                continue
            index_text = field_path.removeprefix("skills[").removesuffix("]")
            try:
                skill = context.candidate.get("skills", [])[int(index_text)]
            except (ValueError, IndexError, TypeError):
                continue
            evidence = skill.get("evidence") if isinstance(skill, dict) else None
            value = evidence or skill
            path = f"{field_path}.evidence" if evidence else field_path
            refs.append({
                "source": "candidate",
                "field_path": path,
                "snippet": _snippet(value),
                "evidence_grade": _evidence_grade("candidate", value),
                "verified": False,
            })

    records = {"candidate": context.candidate, "job": context.job}
    for source, field_path in METRIC_SOURCE_FIELDS.get(indicator_id, []):
        value = records[source].get(field_path)
        if not _nonempty(value):
            continue
        refs.append({
            "source": source,
            "field_path": field_path,
            "snippet": _snippet(value),
            "evidence_grade": _evidence_grade(source, value),
            "verified": False,
        })

    unique: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for ref in refs:
        key = (ref["source"], ref["field_path"], ref["snippet"])
        unique[key] = ref
    return list(unique.values())[:6]


def _score_side(
    side: str,
    definitions: List[Dict[str, Any]],
    context: MetricContext,
) -> Tuple[float | None, List[Dict[str, Any]], Dict[str, Any]]:
    """计算单侧暂估分，并判断已知数据是否足以进行正式比较。"""
    evaluated: List[Dict[str, Any]] = []
    for definition in definitions:
        indicator_id = definition["id"]
        if indicator_id not in METRIC_FUNCTIONS:
            raise ValueError(f"Excel 启用了尚未实现的指标：{indicator_id}")
        result = evaluate_metric(indicator_id, context)
        effective = _effective_score(result.get("score"), definition.get("missing_policy", "exclude"))
        evaluated.append({"definition": definition, "result": result, "effective": effective})

    denominator = sum(
        float(item["definition"]["coefficient"])
        for item in evaluated
        if item["effective"] is not None and item["definition"]["enabled"] and item["definition"]["coefficient"] > 0
    )
    total_weight = sum(
        float(item["definition"]["coefficient"])
        for item in evaluated
        if item["definition"]["enabled"]
        and item["definition"]["coefficient"] > 0
        and item["result"].get("status") != "not_applicable"
    )
    known_items = [
        item for item in evaluated
        if item["result"].get("score") is not None
        and item["definition"]["enabled"]
        and item["definition"]["coefficient"] > 0
    ]
    known_weight = sum(float(item["definition"]["coefficient"]) for item in known_items)
    known_weight_rate = known_weight / total_weight if total_weight > 0 else 0.0

    dimensions: List[Dict[str, Any]] = []
    for item in evaluated:
        definition, result, effective = item["definition"], item["result"], item["effective"]
        coefficient = float(definition["coefficient"])
        applicable = effective is not None and definition["enabled"] and coefficient > 0 and denominator > 0
        normalized_weight = coefficient / denominator if applicable else 0.0
        dimensions.append({
            "id": definition["id"],
            "name": definition["name"],
            "side": side,
            "category": definition["category"],
            "score": None if result.get("score") is None else round(float(result["score"]) * 100, 2),
            "effective_score": None if effective is None else round(effective * 100, 2),
            "status": result.get("status", "unknown"),
            "coefficient": round(coefficient, 2),
            "weight": round(coefficient, 2),
            "normalized_weight_percent": round(normalized_weight * 100, 2),
            "contribution": None if not applicable else round(effective * normalized_weight * 100, 2),
            "missing_policy": definition.get("missing_policy", "exclude"),
            "calculation_method": definition.get("method", ""),
            "coefficient_source": f"匹配指标配置!A{definition['row']}",
            "detail": result.get("detail"),
            "source_fields": {
                "candidate": [path for source, path in METRIC_SOURCE_FIELDS.get(definition["id"], []) if source == "candidate"],
                "job": [path for source, path in METRIC_SOURCE_FIELDS.get(definition["id"], []) if source == "job"],
            },
            "candidate_field_paths": [path for source, path in METRIC_SOURCE_FIELDS.get(definition["id"], []) if source == "candidate"],
            "job_field_paths": [path for source, path in METRIC_SOURCE_FIELDS.get(definition["id"], []) if source == "job"],
            "evidence_refs": _evidence_refs(definition["id"], context),
        })

    estimate = None
    if denominator > 0:
        estimate = round(sum(float(item["contribution"] or 0) for item in dimensions), 2)
    scorable = bool(
        estimate is not None
        and len(known_items) >= MIN_KNOWN_METRICS
        and known_weight_rate >= MIN_KNOWN_WEIGHT_RATE
    )
    state = {
        "status": "ready_for_review" if scorable else "insufficient_data",
        "estimate": estimate,
        "known_metrics": len(known_items),
        "total_metrics": sum(item["result"].get("status") != "not_applicable" for item in evaluated),
        "known_weight": round(known_weight, 2),
        "total_weight": round(total_weight, 2),
        "known_weight_rate": round(known_weight_rate * 100, 2),
        "minimum_known_metrics": MIN_KNOWN_METRICS,
        "minimum_known_weight_rate": round(MIN_KNOWN_WEIGHT_RATE * 100, 2),
        "scorable": scorable,
    }
    return estimate if scorable else None, dimensions, state


def _evidence_matrix(context: MetricContext, recruiter_dimensions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in context.required_rows:
        rows.append({"type": "required_skill", **row})
    for row in context.preferred_rows:
        rows.append({"type": "preferred_skill", **row})
    responsibility = next((item for item in recruiter_dimensions if item["id"] == "responsibility_overlap"), None)
    if responsibility and isinstance(responsibility.get("detail"), list):
        rows.extend({"type": "responsibility", **row} for row in responsibility["detail"])
    return rows


def score_all(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    config: Dict[str, Any],
    as_of_date: Any = None,
) -> Tuple[float | None, List[Dict[str, Any]], Dict[str, Any], float | None, List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """计算双侧结果，并同时返回两侧数据充分性状态。"""
    context = MetricContext(candidate, job, as_of_date)
    enabled = [item for item in config["metrics"] if item.get("enabled") and item.get("coefficient", 0) >= 0]
    recruiter_definitions = [item for item in enabled if item["side"] == "recruiter"]
    candidate_definitions = [item for item in enabled if item["side"] == "candidate"]
    recruiter_score, recruiter_dimensions, recruiter_state = _score_side("recruiter", recruiter_definitions, context)
    candidate_score, candidate_dimensions, candidate_state = _score_side("candidate", candidate_definitions, context)
    matrix = _evidence_matrix(context, recruiter_dimensions)
    return recruiter_score, recruiter_dimensions, recruiter_state, candidate_score, candidate_dimensions, candidate_state, matrix
