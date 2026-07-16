"""本模块校验候选人和岗位的结构、字段类型、硬条件及必要输入。"""

from __future__ import annotations

from typing import Any, Dict, List


def validate_candidate(candidate: Dict[str, Any]) -> Dict[str, List[str]]:
    errors, warnings = [], []
    if not isinstance(candidate, dict):
        return {"errors": ["candidate_must_be_object"], "warnings": []}
    if not candidate.get("skills") and not candidate.get("source_text"):
        warnings.append("candidate_has_no_skills_or_source_text")
    if not candidate.get("target_roles"):
        warnings.append("candidate_target_role_unknown")
    years = candidate.get("experience_years")
    if years is not None and (not isinstance(years, (int, float)) or years < 0 or years > 80):
        errors.append("candidate_experience_years_out_of_range")
    for index, skill in enumerate(candidate.get("skills", [])):
        if not isinstance(skill, dict) or not skill.get("name"):
            errors.append(f"candidate_skill_{index}_missing_name")
    return {"errors": errors, "warnings": warnings}


def validate_job(job: Dict[str, Any]) -> Dict[str, List[str]]:
    errors, warnings = [], []
    if not isinstance(job, dict):
        return {"errors": ["job_must_be_object"], "warnings": []}
    if not job.get("title"):
        warnings.append("job_title_unknown")
    if not job.get("required_skills"):
        warnings.append("job_has_no_required_skills")
    years = job.get("min_experience_years")
    if years is not None and (not isinstance(years, (int, float)) or years < 0 or years > 80):
        errors.append("job_min_experience_years_out_of_range")
    for field in ("required_skills", "preferred_skills"):
        for index, skill in enumerate(job.get(field, [])):
            if not isinstance(skill, dict) or not skill.get("name"):
                errors.append(f"job_{field}_{index}_missing_name")
    return {"errors": errors, "warnings": warnings}
