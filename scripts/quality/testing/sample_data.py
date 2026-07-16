"""本文件集中提供回归测试所需的候选人与岗位样例，避免各测试口径漂移。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


BASE_CANDIDATE: Dict[str, Any] = {
    "id": "c-test",
    "target_roles": ["高级数据产品经理"],
    "skills": [
        {"name": "SQL", "level": 4, "years": 5, "last_used_year": 2026, "evidence": "主导指标平台上线，查询效率提升40%"},
        {"name": "Python", "level": 3, "years": 3, "last_used_year": 2026, "evidence": "自动化周报，每周节省8小时"},
        {"name": "需求分析", "level": 4, "years": 5, "evidence": "主持30余次需求评审并跟踪上线结果"},
    ],
    "experience_years": 5,
    "education": [{"level": "bachelor"}],
    "preferred_locations": ["上海"],
    "preferred_work_modes": ["hybrid"],
    "salary_expectation": {"min": 25000, "max": 32000, "currency": "CNY", "period": "month"},
    "employment_types": ["full-time"],
    "values": ["数据驱动"],
    "growth_goals": ["产品战略", "数据治理"],
    "learning_goals": ["行业解决方案"],
}

BASE_JOB: Dict[str, Any] = {
    "id": "j-test",
    "title": "高级数据产品经理",
    "responsibilities": ["建设企业指标平台", "推动跨团队需求交付"],
    "required_skills": [
        {"name": "SQL", "level": 3, "years": 3, "hard": True},
        {"name": "需求分析", "hard": False},
    ],
    "preferred_skills": [{"name": "Python"}],
    "min_experience_years": 4,
    "education": {"min_level": "bachelor", "hard": False},
    "location": "上海",
    "work_modes": ["hybrid"],
    "salary_range": {"min": 26000, "max": 35000, "currency": "CNY", "period": "month"},
    "employment_type": "full-time",
    "values": ["数据驱动"],
    "growth_offerings": ["产品战略", "数据治理"],
    "learning_offerings": ["行业解决方案"],
}


def candidate(**updates: Any) -> Dict[str, Any]:
    """返回可安全修改的候选人样例。"""
    value = deepcopy(BASE_CANDIDATE)
    value.update(updates)
    return value


def job(**updates: Any) -> Dict[str, Any]:
    """返回可安全修改的岗位样例。"""
    value = deepcopy(BASE_JOB)
    value.update(updates)
    return value
