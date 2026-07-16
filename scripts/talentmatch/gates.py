"""本模块对明确标记的硬性条件执行通过、失败或未知三态核验。"""

from __future__ import annotations

from typing import Any, Dict, List

from .model import safe_float
from .ontology import canonicalize, relation


EDUCATION_RANK = {"unknown": 0, "high-school": 1, "associate": 2, "bachelor": 3, "master": 4, "doctorate": 5}


def _candidate_skills_are_known(candidate: Dict[str, Any]) -> bool:
    """只有已提供技能或明确确认空技能时，才能把未命中解释为硬条件失败。"""
    status = str(candidate.get("data_provenance", {}).get("skills", {}).get("status") or "")
    if status:
        return status in {"provided", "explicit_empty"}
    return bool(candidate.get("skills")) or bool(candidate.get("skills_confirmed_complete"))


def _candidate_education(candidate: Dict[str, Any]) -> int | None:
    ranks = []
    for item in candidate.get("education", []):
        level = item.get("level") if isinstance(item, dict) else item
        if level:
            ranks.append(EDUCATION_RANK.get(str(level).casefold(), 0))
    return max(ranks) if ranks else None


def evaluate_gates(candidate: Dict[str, Any], job: Dict[str, Any]) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    candidate_skills = [item.get("name", "") for item in candidate.get("skills", [])]
    candidate_skills_known = _candidate_skills_are_known(candidate)
    hard_group_ids = set()
    for group in job.get("requirement_groups", []):
        if not group.get("hard"):
            continue
        group_id = str(group.get("id") or "unnamed-group")
        hard_group_ids.add(group_id)
        if group.get("needs_confirmation"):
            gates.append({
                "gate": f"required_skill_group:{group_id}",
                "status": "unknown",
                "operator": group.get("operator"),
                "minimum_match_count": group.get("minimum_match_count"),
                "matched_count": None,
                "evidence": [],
                "reason": "ambiguous_requirement_needs_confirmation",
                "ambiguity_reason": group.get("ambiguity_reason") or "unspecified",
            })
            continue
        items = group.get("items", [])
        operator = str(group.get("operator") or "all")
        minimum = len(items) if operator == "all" else max(1, int(group.get("minimum_match_count") or 1))
        matched, evidence = 0, []
        for requirement in items:
            status, _, matched_name = relation(requirement.get("name", ""), candidate_skills)
            if status == "exact":
                matched += 1
            evidence.append({"required": canonicalize(requirement.get("name", "")), "matched": matched_name or None, "status": status})
        gate_status = "unknown" if not candidate_skills_known else "pass" if matched >= minimum else "fail"
        gates.append({
            "gate": f"required_skill_group:{group_id}",
            "status": gate_status,
            "operator": operator,
            "minimum_match_count": minimum,
            "matched_count": matched,
            "evidence": evidence,
            "reason": "explicit_hard_requirement_group",
        })
    for requirement in job.get("required_skills", []):
        if not requirement.get("hard"):
            continue
        if requirement.get("group_id") in hard_group_ids:
            continue
        status, _, matched = relation(requirement.get("name", ""), candidate_skills)
        if not candidate_skills_known:
            gate_status = "unknown"
        elif status == "exact":
            gate_status = "pass"
        else:
            gate_status = "fail"
        gates.append({
            "gate": f"required_skill:{canonicalize(requirement.get('name', ''))}",
            "status": gate_status,
            "evidence": matched or "not_found",
            "reason": "explicit_hard_requirement",
        })
    required_years = safe_float(job.get("min_experience_years"))
    if required_years is not None and job.get("experience_hard"):
        actual = safe_float(candidate.get("experience_years"))
        status = "unknown" if actual is None else "pass" if actual >= required_years else "fail"
        gates.append({"gate": "minimum_experience", "status": status, "evidence": actual, "required": required_years, "reason": "explicit_hard_requirement"})
    education = job.get("education", {})
    if education.get("hard") and education.get("min_level"):
        required_rank = EDUCATION_RANK.get(str(education["min_level"]).casefold(), 0)
        actual_rank = _candidate_education(candidate)
        status = "unknown" if actual_rank is None else "pass" if actual_rank >= required_rank else "fail"
        gates.append({"gate": "minimum_education", "status": status, "evidence_rank": actual_rank, "required": education["min_level"], "reason": "explicit_hard_requirement"})
    return gates
