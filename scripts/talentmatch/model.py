"""本模块定义候选人和岗位数据的默认结构、规范化规则及常用类型转换。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CANDIDATE_DEFAULTS: Dict[str, Any] = {
    "id": "candidate",
    "target_roles": [],
    "summary": "",
    "skills": [],
    "experience_years": None,
    "experiences": [],
    "education": [],
    "certifications": [],
    "languages": [],
    "preferred_locations": [],
    "preferred_work_modes": [],
    "salary_expectation": {},
    "employment_types": [],
    "availability": None,
    "values": [],
    "growth_goals": [],
    "learning_goals": [],
    "industries": [],
    "industry_experience": [],
    "industry_interests": [],
    "current_seniority": None,
    "desired_seniority": None,
    "project_complexity": None,
    "leadership_years": None,
    "collaboration_evidence": [],
    "preferred_workload": None,
    "travel_preference": None,
    "team_culture_preferences": [],
    "role_stability_preference": None,
    "benefit_preferences": [],
    "manager_style_preferences": [],
    "career_path_goals": [],
    "transferable_skills": [],
    "toolchains": [],
    "domain_knowledge": [],
    "ownership_evidence": [],
    "problem_solving_evidence": [],
    "communication_evidence": [],
    "stakeholder_evidence": [],
    "delivery_evidence": [],
    "innovation_evidence": [],
    "risk_management_evidence": [],
    "learning_evidence": [],
    "adaptability_evidence": [],
    "decision_evidence": [],
    "analytical_evidence": [],
    "customer_evidence": [],
    "compliance_evidence": [],
    "role_mission_preferences": [],
    "daily_task_interests": [],
    "autonomy_preference": None,
    "feedback_frequency_preference": None,
    "collaboration_style_preferences": [],
    "decision_style_preferences": [],
    "pace_preference": None,
    "innovation_environment_preferences": [],
    "learning_budget_expectation": None,
    "mentorship_preferences": [],
    "promotion_clarity_preference": None,
    "compensation_structure_preferences": [],
    "bonus_expectation": {},
    "min_annual_leave_days": None,
    "schedule_flexibility_preferences": [],
    "max_commute_minutes": None,
    "max_travel_days_per_month": None,
    "job_security_preference": None,
    "purpose_preferences": [],
    "psychological_safety_preferences": [],
    "skills_confirmed_complete": False,
    "data_provenance": {},
    "source_text": "",
    "parser": {"mode": "structured", "certainty": 1.0, "warnings": []},
}

JOB_DEFAULTS: Dict[str, Any] = {
    "id": "job",
    "title": "",
    "summary": "",
    "responsibilities": [],
    "required_skills": [],
    "preferred_skills": [],
    "requirement_groups": [],
    "min_experience_years": None,
    "experience_hard": False,
    "education": {},
    "certifications": [],
    "languages": [],
    "location": None,
    "work_modes": [],
    "salary_range": {},
    "employment_type": None,
    "availability_required": None,
    "values": [],
    "growth_offerings": [],
    "learning_offerings": [],
    "industries": [],
    "seniority": None,
    "project_complexity_required": None,
    "leadership_required_years": None,
    "collaboration_requirements": [],
    "workload": None,
    "travel_requirement": None,
    "team_culture": [],
    "role_stability": None,
    "benefits": [],
    "manager_style": [],
    "career_paths": [],
    "transferable_skill_requirements": [],
    "toolchains": [],
    "domain_knowledge": [],
    "ownership_expectations": [],
    "problem_solving_expectations": [],
    "communication_expectations": [],
    "stakeholder_expectations": [],
    "delivery_expectations": [],
    "innovation_expectations": [],
    "risk_management_expectations": [],
    "learning_agility_expectations": [],
    "adaptability_expectations": [],
    "decision_quality_expectations": [],
    "analytical_expectations": [],
    "customer_orientation_expectations": [],
    "compliance_expectations": [],
    "role_mission": [],
    "daily_tasks": [],
    "autonomy_level": None,
    "feedback_frequency": None,
    "collaboration_style": [],
    "decision_style": [],
    "pace": None,
    "innovation_environment": [],
    "learning_budget": None,
    "mentorship": [],
    "promotion_clarity": None,
    "compensation_structure": [],
    "bonus_range": {},
    "annual_leave_days": None,
    "schedule_flexibility": [],
    "commute_minutes": None,
    "travel_days_per_month": None,
    "job_security": None,
    "purpose": [],
    "psychological_safety": [],
    "source_text": "",
    "parser": {"mode": "structured", "certainty": 1.0, "warnings": []},
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any, field_name: str = "字段") -> bool:
    """解析常见布尔写法，拒绝含义不明确的值，避免字符串被Python直接视为真。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "是", "真"}:
            return True
        if normalized in {"false", "0", "no", "n", "否", "假", ""}:
            return False
    if value is None:
        return False
    raise ValueError(f"{field_name}必须是布尔值，可使用 true/false、1/0、yes/no 或 是/否")


def as_list(value: Any) -> List[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def clean_strings(values: Iterable[Any]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def normalize_skill_item(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {"name": item, "level": None, "years": None, "evidence": "", "hard": False, "weight": 1.0}
    if not isinstance(item, dict):
        return {"name": str(item), "level": None, "years": None, "evidence": "", "hard": False, "weight": 1.0}
    output = dict(item)
    output["name"] = str(output.get("name", "")).strip()
    output["level"] = safe_float(output.get("level"))
    output["years"] = safe_float(output.get("years"))
    output["evidence"] = str(output.get("evidence", "")).strip()
    output["hard"] = parse_bool(output.get("hard", False), "skills[].hard")
    output["weight"] = max(0.1, safe_float(output.get("weight"), 1.0) or 1.0)
    output["last_used_year"] = safe_float(output.get("last_used_year"))
    if output.get("group_id") not in (None, ""):
        output["group_id"] = str(output["group_id"]).strip()
    if output.get("group_operator") not in (None, ""):
        operator = str(output["group_operator"]).strip().casefold()
        output["group_operator"] = operator if operator in {"all", "any"} else "all"
    if output.get("group_minimum_match_count") not in (None, ""):
        output["group_minimum_match_count"] = max(1, int(safe_float(output["group_minimum_match_count"], 1) or 1))
    return output


def normalize_requirement_group(item: Any, index: int) -> Dict[str, Any]:
    """统一岗位技能逻辑组，供解析、评分和硬门槛核验共用。"""
    if not isinstance(item, dict):
        raise ValueError("requirement_groups[] 必须是对象")
    group = dict(item)
    group_id = str(group.get("id") or f"requirement-group-{index + 1}").strip()
    operator = str(group.get("operator") or "all").strip().casefold()
    if operator not in {"all", "any"}:
        raise ValueError(f"requirement_groups[{index}].operator 只能是 all 或 any")
    items = [normalize_skill_item(value) for value in as_list(group.get("items")) if str(value).strip()]
    if not items:
        raise ValueError(f"requirement_groups[{index}].items 不能为空")
    requested = safe_float(group.get("minimum_match_count"))
    minimum = len(items) if operator == "all" else int(requested or 1)
    minimum = max(1, min(len(items), int(minimum)))
    hard = parse_bool(group.get("hard", False), f"requirement_groups[{index}].hard")
    for skill in items:
        skill["group_id"] = group_id
        skill["group_operator"] = operator
        skill["group_minimum_match_count"] = minimum
        skill["hard"] = hard or skill.get("hard", False)
    return {
        "id": group_id,
        "operator": operator,
        "minimum_match_count": minimum,
        "items": items,
        "hard": hard,
        "preferred": parse_bool(group.get("preferred", False), f"requirement_groups[{index}].preferred"),
        "needs_confirmation": parse_bool(group.get("needs_confirmation", False), f"requirement_groups[{index}].needs_confirmation"),
        "ambiguity_reason": str(group.get("ambiguity_reason", "")).strip(),
        "weight": max(0.1, safe_float(group.get("weight"), 1.0) or 1.0),
        "source": str(group.get("source", "")).strip(),
    }


def normalize_candidate(data: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(CANDIDATE_DEFAULTS)
    result.update(data or {})
    result["id"] = str(result.get("id") or "candidate")
    result["target_roles"] = clean_strings(as_list(result.get("target_roles")))
    result["skills"] = [normalize_skill_item(x) for x in as_list(result.get("skills")) if str(x).strip()]
    result["skills_confirmed_complete"] = parse_bool(result.get("skills_confirmed_complete", False), "skills_confirmed_complete")
    provenance = result.get("data_provenance") if isinstance(result.get("data_provenance"), dict) else {}
    provenance = deepcopy(provenance)
    if not isinstance(provenance.get("skills"), dict):
        if result["skills"]:
            skill_status, confidence = "provided", 1.0
        elif result["skills_confirmed_complete"]:
            skill_status, confidence = "explicit_empty", 1.0
        else:
            skill_status, confidence = "inferred", 0.25
        provenance["skills"] = {
            "status": skill_status,
            "source": "candidate_input",
            "confidence": confidence,
        }
    result["data_provenance"] = provenance
    result["experience_years"] = safe_float(result.get("experience_years"))
    for field in ("experiences", "education", "certifications", "languages"):
        result[field] = as_list(result.get(field))
    for field in (
        "preferred_locations", "preferred_work_modes", "employment_types", "values", "growth_goals",
        "learning_goals", "industries", "industry_interests", "collaboration_evidence",
        "team_culture_preferences", "benefit_preferences", "manager_style_preferences", "career_path_goals",
        "transferable_skills", "toolchains", "domain_knowledge", "ownership_evidence",
        "problem_solving_evidence", "communication_evidence", "stakeholder_evidence", "delivery_evidence",
        "innovation_evidence", "risk_management_evidence", "learning_evidence", "adaptability_evidence",
        "decision_evidence", "analytical_evidence", "customer_evidence", "compliance_evidence",
        "role_mission_preferences", "daily_task_interests", "collaboration_style_preferences",
        "decision_style_preferences", "innovation_environment_preferences", "mentorship_preferences",
        "compensation_structure_preferences", "schedule_flexibility_preferences", "purpose_preferences",
        "psychological_safety_preferences",
    ):
        result[field] = clean_strings(as_list(result.get(field)))
    result["industry_experience"] = as_list(result.get("industry_experience"))
    for field in (
        "project_complexity", "leadership_years", "learning_budget_expectation",
        "min_annual_leave_days", "max_commute_minutes", "max_travel_days_per_month",
    ):
        result[field] = safe_float(result.get(field))
    result["salary_expectation"] = result.get("salary_expectation") if isinstance(result.get("salary_expectation"), dict) else {}
    result["bonus_expectation"] = result.get("bonus_expectation") if isinstance(result.get("bonus_expectation"), dict) else {}
    result["parser"] = result.get("parser") if isinstance(result.get("parser"), dict) else deepcopy(CANDIDATE_DEFAULTS["parser"])
    return result


def normalize_job(data: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(JOB_DEFAULTS)
    result.update(data or {})
    result["id"] = str(result.get("id") or "job")
    result["title"] = str(result.get("title") or "").strip()
    result["responsibilities"] = clean_strings(as_list(result.get("responsibilities")))
    result["required_skills"] = [normalize_skill_item(x) for x in as_list(result.get("required_skills")) if str(x).strip()]
    result["preferred_skills"] = [normalize_skill_item(x) for x in as_list(result.get("preferred_skills")) if str(x).strip()]
    raw_groups = as_list(result.get("requirement_groups"))
    result["requirement_groups"] = [normalize_requirement_group(item, index) for index, item in enumerate(raw_groups)]
    if result["requirement_groups"]:
        grouped_ids = {
            (skill.get("group_id"), skill.get("name"))
            for skill in result["required_skills"] + result["preferred_skills"]
            if skill.get("group_id")
        }
        for group in result["requirement_groups"]:
            target = result["preferred_skills"] if group["preferred"] else result["required_skills"]
            for skill in group["items"]:
                identity = (skill.get("group_id"), skill.get("name"))
                if identity not in grouped_ids:
                    target.append(dict(skill))
                    grouped_ids.add(identity)
    result["min_experience_years"] = safe_float(result.get("min_experience_years"))
    result["experience_hard"] = parse_bool(result.get("experience_hard", False), "experience_hard")
    result["education"] = result.get("education") if isinstance(result.get("education"), dict) else {}
    if result["education"]:
        result["education"] = dict(result["education"])
        result["education"]["hard"] = parse_bool(result["education"].get("hard", False), "education.hard")
    for field in ("certifications", "languages"):
        result[field] = as_list(result.get(field))
    for field in (
        "work_modes", "values", "growth_offerings", "learning_offerings", "industries",
        "collaboration_requirements", "team_culture", "benefits", "manager_style", "career_paths",
        "transferable_skill_requirements", "toolchains", "domain_knowledge", "ownership_expectations",
        "problem_solving_expectations", "communication_expectations", "stakeholder_expectations",
        "delivery_expectations", "innovation_expectations", "risk_management_expectations",
        "learning_agility_expectations", "adaptability_expectations", "decision_quality_expectations",
        "analytical_expectations", "customer_orientation_expectations", "compliance_expectations",
        "role_mission", "daily_tasks", "collaboration_style", "decision_style", "innovation_environment",
        "mentorship", "compensation_structure", "schedule_flexibility", "purpose", "psychological_safety",
    ):
        result[field] = clean_strings(as_list(result.get(field)))
    for field in (
        "project_complexity_required", "leadership_required_years", "learning_budget",
        "annual_leave_days", "commute_minutes", "travel_days_per_month",
    ):
        result[field] = safe_float(result.get(field))
    result["salary_range"] = result.get("salary_range") if isinstance(result.get("salary_range"), dict) else {}
    result["bonus_range"] = result.get("bonus_range") if isinstance(result.get("bonus_range"), dict) else {}
    result["parser"] = result.get("parser") if isinstance(result.get("parser"), dict) else deepcopy(JOB_DEFAULTS["parser"])
    return result
