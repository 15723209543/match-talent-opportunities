"""本模块检查岗位说明质量、公平性和用于匹配的字段完整程度。"""

from __future__ import annotations

from typing import Any, Dict, List

from .fairness import audit_text
from .ontology import canonicalize
from .parser import parse_job


def audit_job(value: Any) -> Dict[str, Any]:
    job = parse_job(value)
    source = job.get("source_text", "")
    fairness = audit_text(source)
    issues: List[Dict[str, str]] = []
    if not job.get("title"):
        issues.append({"severity": "high", "code": "missing_title", "advice": "补充唯一、清晰、不过度夸张的岗位名称"})
    if len(job.get("responsibilities", [])) < 3:
        issues.append({"severity": "medium", "code": "thin_responsibilities", "advice": "补充3-6条可交付、可观察的核心职责"})
    if not job.get("required_skills"):
        issues.append({"severity": "high", "code": "missing_required_skills", "advice": "区分必需技能与加分技能"})
    if not job.get("salary_range"):
        issues.append({"severity": "low", "code": "salary_not_disclosed", "advice": "若政策允许，提供薪酬范围、币种和周期"})
    hard_count = sum(item.get("hard") for item in job.get("required_skills", []))
    if hard_count > 5:
        issues.append({"severity": "medium", "code": "too_many_hard_filters", "advice": "复核硬性条件，只保留无法通过入职后学习补齐的条件"})
    skills = [canonicalize(item.get("name", "")) for item in job.get("required_skills", []) + job.get("preferred_skills", [])]
    if len(skills) != len(set(skills)):
        issues.append({"severity": "low", "code": "duplicate_skills", "advice": "合并重复或同义技能"})
    if fairness["protected_trait_flags"]:
        issues.append({"severity": "critical", "code": "protected_trait_criteria", "advice": "删除与岗位胜任力无关的受保护属性限制并进行合规复核"})
    return {"job_id": job.get("id"), "quality_score": max(0, 100 - sum({"low": 5, "medium": 12, "high": 20, "critical": 35}[x["severity"]] for x in issues)), "issues": issues, "fairness": fairness}
