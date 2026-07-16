"""本模块实现企业侧42项和求职者侧38项匹配指标的实际计算函数。"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .gates import EDUCATION_RANK
from .model import clamp, parse_bool, safe_float
from .ontology import canonicalize, relation
from .text import list_overlap, quantified_evidence, safe_mean, weighted_overlap


MetricValue = Dict[str, Any]
MetricFunction = Callable[["MetricContext"], MetricValue]


def parse_calendar_date(value_to_parse: Any) -> date | None:
    """解析YYYY-MM-DD或YYYY-M-D；无效日期返回None。"""
    if isinstance(value_to_parse, datetime):
        return value_to_parse.date()
    if isinstance(value_to_parse, date):
        return value_to_parse
    text = str(value_to_parse or "").strip()
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def resolve_as_of_date(value_to_parse: Any = None) -> date:
    """确定本次评分基准日；显式传入的无效日期会被拒绝。"""
    if value_to_parse in (None, ""):
        return date.today()
    parsed = parse_calendar_date(value_to_parse)
    if parsed is None:
        raise ValueError("as_of_date必须是有效的YYYY-MM-DD日期")
    return parsed


def value(score: Optional[float], detail: Any = None, status: Optional[str] = None) -> MetricValue:
    if score is None:
        return {"score": None, "status": status or "unknown", "detail": detail}
    bounded = clamp(float(score))
    label = status or ("met" if bounded >= 0.8 else "partial" if bounded >= 0.5 else "gap")
    return {"score": bounded, "status": label, "detail": detail}


def _items(values: Iterable[Any]) -> List[str]:
    output = []
    for item in values or []:
        if isinstance(item, dict):
            text = item.get("name") or item.get("title") or item.get("industry") or ""
        else:
            text = item
        if str(text).strip():
            output.append(str(text).strip())
    return output


def _overlap(left: Iterable[Any], right: Iterable[Any], detail: Any = None) -> MetricValue:
    left_values, right_values = list(left or []), list(right or [])
    score = list_overlap(left_values, right_values)
    return value(score, detail or {"candidate": left_values, "job": right_values})


def _ordered_fit(candidate_value: Any, job_value: Any, mapping: Dict[str, int]) -> MetricValue:
    if candidate_value in (None, "") or job_value in (None, ""):
        return value(None, {"candidate": candidate_value, "job": job_value})
    candidate_rank = mapping.get(str(candidate_value).strip().casefold())
    job_rank = mapping.get(str(job_value).strip().casefold())
    if candidate_rank is None or job_rank is None:
        return value(None, {"candidate": candidate_value, "job": job_value, "reason": "unrecognized_level"})
    if candidate_rank >= job_rank:
        score = 1.0
    else:
        score = clamp(candidate_rank / max(job_rank, 1), 0.2, 1.0)
    return value(score, {"candidate": candidate_value, "job": job_value})


class MetricContext:
    def __init__(self, candidate: Dict[str, Any], job: Dict[str, Any], as_of_date: Any = None):
        self.candidate = candidate
        self.job = job
        self.as_of_date = resolve_as_of_date(as_of_date)
        skill_state = str(candidate.get("data_provenance", {}).get("skills", {}).get("status") or "")
        self.candidate_skill_state = skill_state or ("provided" if candidate.get("skills") else "omitted")
        self.candidate_skills_known = self.candidate_skill_state in {"provided", "explicit_empty"}
        self.candidate_skill_map = {
            canonicalize(item.get("name", "")): item
            for item in candidate.get("skills", [])
            if isinstance(item, dict) and item.get("name")
        }
        self.candidate_skill_index = {
            canonicalize(item.get("name", "")): index
            for index, item in enumerate(candidate.get("skills", []))
            if isinstance(item, dict) and item.get("name")
        }
        self.required_rows = self._skill_rows(job.get("required_skills", []))
        self.preferred_rows = self._skill_rows(job.get("preferred_skills", []))

    def _skill_rows(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        candidate_names = list(self.candidate_skill_map)
        for requirement in requirements:
            required_name = canonicalize(requirement.get("name", ""))
            if self.candidate_skills_known:
                relation_status, relation_score, matched_name = relation(required_name, candidate_names)
            else:
                relation_status, relation_score, matched_name = "unknown", None, ""
            candidate_skill = self.candidate_skill_map.get(matched_name, {})
            candidate_skill_index = self.candidate_skill_index.get(matched_name)
            required_level = safe_float(requirement.get("level"))
            actual_level = safe_float(candidate_skill.get("level"))
            required_years = safe_float(requirement.get("years"))
            actual_years = safe_float(candidate_skill.get("years"))
            evidence = str(candidate_skill.get("evidence", ""))
            last_used = safe_float(candidate_skill.get("last_used_year"))

            level_score = None
            if relation_status != "missing" and required_level is not None and actual_level is not None:
                level_score = clamp(actual_level / max(required_level, 1.0), 0.2, 1.0)
            years_score = None
            if relation_status != "missing" and required_years is not None and actual_years is not None:
                years_score = clamp(actual_years / max(required_years, 0.5), 0.2, 1.0)
            recency_score = None
            if relation_status != "missing" and last_used is not None:
                inactive_years = max(0.0, self.as_of_date.year - last_used)
                recency_score = 1.0 if inactive_years <= 1 else 0.8 if inactive_years <= 2 else 0.5 if inactive_years <= 4 else 0.2
            evidence_score = quantified_evidence(evidence) if evidence else None
            impact_score = None
            if evidence:
                has_number = bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|％|万|亿|k|m|人|个|天|月|年|小时)", evidence, re.I))
                has_result = bool(re.search(r"提升|降低|增长|节省|上线|交付|转化|营收|improv|reduc|increas|launch|deliver|revenue", evidence, re.I))
                impact_score = 1.0 if has_number and has_result else 0.65 if has_number or has_result else 0.3
            factors = [] if relation_score is None else [relation_score]
            factors.extend(x for x in (level_score, years_score, evidence_score) if x is not None)
            if relation_status == "missing":
                item_score = 0.0
            elif factors:
                item_score = safe_mean(factors, relation_score or 0.0)
            else:
                item_score = None
            rows.append({
                "requirement": required_name,
                "matched_skill": matched_name or None,
                "candidate_field_path": f"skills[{candidate_skill_index}]" if candidate_skill_index is not None else None,
                "status": relation_status,
                "evidence": evidence[:180] if evidence else "not_provided",
                "coverage_score": relation_score,
                "level_score": level_score,
                "years_score": years_score,
                "recency_score": recency_score,
                "evidence_score": evidence_score,
                "impact_score": impact_score,
                "item_score": None if item_score is None else round(item_score * 100, 2),
                "requirement_weight": max(0.1, safe_float(requirement.get("weight"), 1.0) or 1.0),
                "hard": parse_bool(requirement.get("hard", False), "required_skills[].hard"),
                "group_id": requirement.get("group_id"),
                "group_operator": requirement.get("group_operator", "all"),
                "group_minimum_match_count": int(safe_float(requirement.get("group_minimum_match_count"), 1) or 1),
            })
        return rows


def _weighted_skill_part(rows: List[Dict[str, Any]], key: str, empty: Optional[float] = None) -> MetricValue:
    if not rows:
        return value(empty, {"requirements": 0}, "not_applicable" if empty is None else None)
    ungrouped = []
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("group_id"):
            grouped.setdefault(str(row["group_id"]), []).append(row)
        elif row.get(key) is not None:
            ungrouped.append((float(row[key]), row["requirement_weight"], row["requirement"]))

    units = list(ungrouped)
    group_details = []
    for group_id, members in grouped.items():
        applicable_scores = [float(row[key]) for row in members if row.get(key) is not None]
        if not applicable_scores:
            continue
        operator = str(members[0].get("group_operator") or "all")
        minimum = max(1, min(len(members), int(members[0].get("group_minimum_match_count") or 1)))
        if operator == "any":
            selected = sorted(applicable_scores, reverse=True)[:minimum]
            if len(selected) < minimum:
                selected.extend([0.0] * (minimum - len(selected)))
        else:
            selected = applicable_scores
        group_score = safe_mean(selected, 0.0)
        group_weight = safe_mean([row["requirement_weight"] for row in members], 1.0)
        units.append((group_score, group_weight, group_id))
        group_details.append({
            "group_id": group_id,
            "operator": operator,
            "minimum_match_count": minimum,
            "score": round(group_score * 100, 2),
            "members": [row["requirement"] for row in members],
        })
    if not units:
        return value(None, {"requirements": len(rows), "applicable": 0})
    numerator = sum(score * weight for score, weight, _ in units)
    denominator = sum(weight for _, weight, _ in units)
    return value(numerator / denominator, {
        "requirements": len(rows),
        "scoring_units": len(units),
        "groups": group_details,
    })


def _responsibility(ctx: MetricContext) -> MetricValue:
    requirements = ctx.job.get("responsibilities", [])
    if not requirements:
        return value(None, {"requirements": 0})
    evidence = [ctx.candidate.get("summary", ""), ctx.candidate.get("source_text", "")]
    for skill in ctx.candidate.get("skills", []):
        evidence.append(str(skill.get("evidence", "")))
    for experience in ctx.candidate.get("experiences", []):
        if isinstance(experience, dict):
            evidence.extend([experience.get("title", ""), " ".join(map(str, experience.get("achievements", [])))])
        else:
            evidence.append(str(experience))
    evidence = [str(item) for item in evidence if str(item).strip()]
    rows = []
    for requirement in requirements:
        raw = max((weighted_overlap(item, requirement) for item in evidence), default=0.0)
        score = clamp(raw * 2.4)
        rows.append({"requirement": str(requirement)[:180], "status": "supported" if score >= 0.6 else "partial" if score >= 0.25 else "unverified", "item_score": round(score * 100, 2)})
    return value(safe_mean([row["item_score"] / 100 for row in rows]), rows)


def _experience(ctx: MetricContext) -> MetricValue:
    required = safe_float(ctx.job.get("min_experience_years"))
    actual = safe_float(ctx.candidate.get("experience_years"))
    if required is None or actual is None:
        return value(None, {"actual": actual, "required": required})
    return value(clamp(actual / max(required, 0.5)), {"actual": actual, "required": required})


def _education(ctx: MetricContext) -> MetricValue:
    required = ctx.job.get("education", {}).get("min_level")
    levels = []
    for item in ctx.candidate.get("education", []):
        level = item.get("level") if isinstance(item, dict) else item
        if level:
            levels.append(str(level).casefold())
    if not required or not levels:
        return value(None, {"candidate": levels, "required": required})
    actual_rank = max(EDUCATION_RANK.get(level, 0) for level in levels)
    required_rank = EDUCATION_RANK.get(str(required).casefold(), 0)
    if required_rank <= 0:
        return value(None, {"candidate": levels, "required": required})
    return value(clamp(actual_rank / required_rank, 0.2, 1.0), {"candidate_rank": actual_rank, "required_rank": required_rank})


def _named_qualification(candidate_values: Iterable[Any], job_values: Iterable[Any]) -> MetricValue:
    return _overlap(_items(candidate_values), _items(job_values))


def _availability(ctx: MetricContext) -> MetricValue:
    actual, required = ctx.candidate.get("availability"), ctx.job.get("availability_required")
    if not actual or not required:
        return value(None, {"candidate": actual, "required": required})
    actual_date = parse_calendar_date(actual)
    required_date = parse_calendar_date(required)
    if actual_date is None or required_date is None:
        return value(None, {"candidate": actual, "required": required, "reason": "invalid_date_format"})
    return value(1.0 if actual_date <= required_date else 0.0, {
        "candidate": actual_date.isoformat(),
        "required": required_date.isoformat(),
    })


def _salary(ctx: MetricContext) -> MetricValue:
    expectation, salary_range = ctx.candidate.get("salary_expectation", {}), ctx.job.get("salary_range", {})
    if not expectation or not salary_range:
        return value(None, {"reason": "salary_missing"})
    if expectation.get("currency", "CNY") != salary_range.get("currency", "CNY") or expectation.get("period", "month") != salary_range.get("period", "month"):
        return value(None, {"reason": "currency_or_period_mismatch"})
    e_min, e_max = safe_float(expectation.get("min")), safe_float(expectation.get("max"))
    j_min, j_max = safe_float(salary_range.get("min")), safe_float(salary_range.get("max"))
    if (e_min is None and e_max is None) or (j_min is None and j_max is None):
        return value(None, {"reason": "salary_range_invalid"})
    if e_min is not None and e_max is not None and e_max < e_min:
        return value(None, {"reason": "salary_range_invalid"})
    if j_min is not None and j_max is not None and j_max < j_min:
        return value(None, {"reason": "salary_range_invalid"})
    if None in (e_min, e_max, j_min, j_max):
        e_low, e_high = (-math.inf if e_min is None else e_min), (math.inf if e_max is None else e_max)
        j_low, j_high = (-math.inf if j_min is None else j_min), (math.inf if j_max is None else j_max)
        if max(e_low, j_low) <= min(e_high, j_high):
            comparable_bounds = []
            if e_min is not None and j_min is not None:
                comparable_bounds.append(1.0 - abs(e_min - j_min) / max(e_min, j_min, 1.0))
            if e_max is not None and j_max is not None:
                comparable_bounds.append(1.0 - abs(e_max - j_max) / max(e_max, j_max, 1.0))
            score = 0.85 + 0.15 * (sum(comparable_bounds) / len(comparable_bounds) if comparable_bounds else 0.5)
        else:
            gap = j_low - e_high if e_high < j_low else e_low - j_high
            finite_bounds = [item for item in (e_min, e_max, j_min, j_max) if item is not None]
            score = clamp(0.55 - gap / max(max(finite_bounds, default=1.0), 1.0))
        return value(score, {"expectation": expectation, "salary_range": salary_range, "open_interval": True})
    intersection_low = max(e_min, j_min)
    intersection_high = min(e_max, j_max)
    intersects = intersection_low <= intersection_high
    overlap = max(0.0, intersection_high - intersection_low)
    union = max(e_max, j_max) - min(e_min, j_min)
    if overlap > 0:
        score = clamp(0.65 + 0.35 * overlap / max(union, 1.0))
    elif intersects:
        score = 1.0 if e_min == e_max == j_min == j_max else 0.8
    else:
        gap = min(abs(e_min - j_max), abs(j_min - e_max))
        scale = max(e_max - e_min, j_max - j_min, 1.0)
        score = clamp(0.55 - gap / (2 * scale))
    return value(score, {
        "expectation": expectation,
        "salary_range": salary_range,
        "boundary_touch": bool(intersects and overlap == 0 and not (e_min == e_max == j_min == j_max)),
    })


def _role(ctx: MetricContext) -> MetricValue:
    roles, title = ctx.candidate.get("target_roles", []), ctx.job.get("title", "")
    if not roles or not title:
        return value(None, {"candidate_roles": roles, "job_title": title})
    exact = any(title.casefold() in role.casefold() or role.casefold() in title.casefold() for role in roles)
    score = 1.0 if exact else clamp(max(weighted_overlap(role, title) * 2 for role in roles))
    return value(score, {"candidate_roles": roles, "job_title": title})


def _numeric_requirement(ctx: MetricContext, candidate_key: str, job_key: str) -> MetricValue:
    actual, required = safe_float(ctx.candidate.get(candidate_key)), safe_float(ctx.job.get(job_key))
    if actual is None or required is None:
        return value(None, {"actual": actual, "required": required})
    return value(clamp(actual / max(required, 0.5), 0.2, 1.0), {"actual": actual, "required": required})


def _industry(ctx: MetricContext) -> MetricValue:
    candidate_industries = list(ctx.candidate.get("industries", []))
    candidate_industries.extend(_items(ctx.candidate.get("industry_experience", [])))
    return _overlap(candidate_industries, ctx.job.get("industries", []))


def _collaboration(ctx: MetricContext) -> MetricValue:
    requirements = ctx.job.get("collaboration_requirements", [])
    evidence = ctx.candidate.get("collaboration_evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not requirements or not evidence:
        return value(None, {"candidate": evidence, "job": requirements})
    scores = [max((weighted_overlap(item, requirement) for item in evidence), default=0.0) for requirement in requirements]
    return value(clamp(safe_mean(scores) * 2.4), {"candidate": evidence, "job": requirements})


def _skill_evidence(ctx: MetricContext, key: str) -> MetricValue:
    rows = [row for row in ctx.required_rows + ctx.preferred_rows if row.get("status") != "missing"]
    return _weighted_skill_part(rows, key)


def _candidate_seniority(ctx: MetricContext) -> MetricValue:
    desired = ctx.candidate.get("desired_seniority") or ctx.candidate.get("current_seniority")
    offered = ctx.job.get("seniority")
    mapping = {"intern": 1, "实习": 1, "junior": 2, "初级": 2, "mid": 3, "中级": 3, "senior": 4, "高级": 4, "lead": 5, "负责人": 5, "manager": 6, "经理": 6, "director": 7, "总监": 7}
    if not desired or not offered:
        return value(None, {"desired": desired, "offered": offered})
    d_rank, o_rank = mapping.get(str(desired).casefold()), mapping.get(str(offered).casefold())
    if d_rank is None or o_rank is None:
        return value(list_overlap([desired], [offered]), {"desired": desired, "offered": offered})
    distance = abs(d_rank - o_rank)
    return value(1.0 if distance == 0 else 0.8 if distance == 1 else 0.45 if distance == 2 else 0.15, {"desired": desired, "offered": offered})


def _preference_order(ctx: MetricContext, candidate_key: str, job_key: str, mapping: Dict[str, int], lower_is_easier: bool = False) -> MetricValue:
    candidate_value, job_value = ctx.candidate.get(candidate_key), ctx.job.get(job_key)
    if candidate_value in (None, "") or job_value in (None, ""):
        return value(None, {"candidate": candidate_value, "job": job_value})
    c_rank = mapping.get(str(candidate_value).strip().casefold())
    j_rank = mapping.get(str(job_value).strip().casefold())
    if c_rank is None or j_rank is None:
        return value(list_overlap([candidate_value], [job_value]), {"candidate": candidate_value, "job": job_value})
    if lower_is_easier:
        score = 1.0 if j_rank <= c_rank else clamp(1 - 0.3 * (j_rank - c_rank))
    else:
        score = 1.0 if j_rank >= c_rank else clamp(1 - 0.3 * (c_rank - j_rank))
    return value(score, {"candidate": candidate_value, "job": job_value})


def _text_evidence_fit(ctx: MetricContext, candidate_key: str, job_key: str) -> MetricValue:
    """Match every job expectation to the strongest candidate evidence fragment."""
    evidence = _items(ctx.candidate.get(candidate_key, []))
    expectations = _items(ctx.job.get(job_key, []))
    if not evidence or not expectations:
        return value(None, {"candidate": evidence, "job": expectations})
    rows = []
    for expectation in expectations:
        raw = max((weighted_overlap(item, expectation) for item in evidence), default=0.0)
        score = clamp(raw * 2.4)
        rows.append({"expectation": expectation, "score": round(score * 100, 2)})
    return value(safe_mean([row["score"] / 100 for row in rows]), rows)


def _skill_breadth(ctx: MetricContext) -> MetricValue:
    if not ctx.candidate_skills_known:
        return value(None, {"reason": "candidate_skills_not_provided", "provenance": ctx.candidate_skill_state})
    rows = ctx.required_rows + ctx.preferred_rows
    if not rows:
        return value(None, {"requirements": 0})
    covered = safe_mean([row.get("coverage_score", 0.0) for row in rows])
    expected_count = max(1, len(rows))
    breadth = clamp(len(ctx.candidate_skill_map) / expected_count)
    return value(0.75 * covered + 0.25 * breadth, {"matched_coverage": round(covered * 100, 2), "candidate_skill_count": len(ctx.candidate_skill_map), "job_skill_count": len(rows)})


def _core_skill_depth(ctx: MetricContext) -> MetricValue:
    if not ctx.candidate_skills_known:
        return value(None, {"reason": "candidate_skills_not_provided", "provenance": ctx.candidate_skill_state})
    rows = [row for row in ctx.required_rows if row.get("hard")]
    if not rows:
        rows = ctx.required_rows
    if not rows:
        return value(None, {"core_requirements": 0})
    scores = []
    for row in rows:
        factors = [row.get("coverage_score")]
        factors.extend(item for item in (row.get("level_score"), row.get("years_score")) if item is not None)
        scores.append(safe_mean(factors, 0.0))
    return value(safe_mean(scores), {"core_requirements": len(rows), "item_scores": [round(x * 100, 2) for x in scores]})


def _transferable_readiness(ctx: MetricContext) -> MetricValue:
    explicit = _overlap(ctx.candidate.get("transferable_skills", []), ctx.job.get("transferable_skill_requirements", []))
    if explicit.get("score") is not None:
        return explicit
    rows = [row for row in ctx.required_rows + ctx.preferred_rows if row.get("status") == "partial"]
    if not rows:
        return value(None, {"partial_matches": 0})
    return value(safe_mean([row.get("coverage_score", 0.0) for row in rows]), rows)


def _achievement_consistency(ctx: MetricContext) -> MetricValue:
    experiences = [item for item in ctx.candidate.get("experiences", []) if isinstance(item, dict)]
    if not experiences:
        return value(None, {"experience_rows": 0})
    scores = []
    for item in experiences:
        achievements = _items(item.get("achievements", []))
        if not achievements:
            scores.append(0.0)
        else:
            scores.append(0.6 + 0.4 * safe_mean([quantified_evidence(text) for text in achievements]))
    return value(safe_mean(scores), {"experience_rows": len(experiences), "rows_with_achievements": sum(score > 0 for score in scores)})


def _evidence_recency(ctx: MetricContext) -> MetricValue:
    recency = [row["recency_score"] for row in ctx.required_rows + ctx.preferred_rows if row.get("recency_score") is not None]
    if recency:
        return value(safe_mean(recency), {"dated_skills": len(recency)})
    current = [item for item in ctx.candidate.get("experiences", []) if isinstance(item, dict) and str(item.get("end", "")).casefold() in {"present", "至今", "now"}]
    return value(1.0 if current else None, {"current_experience_rows": len(current)})


def _outcome_relevance(ctx: MetricContext) -> MetricValue:
    achievements = []
    for item in ctx.candidate.get("experiences", []):
        if isinstance(item, dict):
            achievements.extend(_items(item.get("achievements", [])))
    achievements.extend(str(skill.get("evidence", "")) for skill in ctx.candidate.get("skills", []) if isinstance(skill, dict) and skill.get("evidence"))
    requirements = _items(ctx.job.get("responsibilities", []))
    if not achievements or not requirements:
        return value(None, {"achievements": len(achievements), "responsibilities": len(requirements)})
    rows = []
    for requirement in requirements:
        best = max(achievements, key=lambda item: weighted_overlap(item, requirement))
        relevance = clamp(weighted_overlap(best, requirement) * 2.4)
        quantified = quantified_evidence(best)
        rows.append(0.7 * relevance + 0.3 * quantified)
    return value(safe_mean(rows), {"matched_responsibilities": len(rows)})


def _minimum_offering(ctx: MetricContext, candidate_key: str, job_key: str) -> MetricValue:
    expected = safe_float(ctx.candidate.get(candidate_key))
    offered = safe_float(ctx.job.get(job_key))
    if expected is None or offered is None:
        return value(None, {"expected_minimum": expected, "offered": offered})
    if expected <= 0:
        return value(1.0, {"expected_minimum": expected, "offered": offered})
    return value(clamp(offered / expected), {"expected_minimum": expected, "offered": offered})


def _maximum_burden(ctx: MetricContext, candidate_key: str, job_key: str) -> MetricValue:
    maximum = safe_float(ctx.candidate.get(candidate_key))
    actual = safe_float(ctx.job.get(job_key))
    if maximum is None or actual is None:
        return value(None, {"candidate_maximum": maximum, "job_actual": actual})
    if actual <= maximum:
        return value(1.0, {"candidate_maximum": maximum, "job_actual": actual})
    return value(clamp(maximum / max(actual, 1.0)), {"candidate_maximum": maximum, "job_actual": actual})


def _range_fit(candidate_range: Dict[str, Any], job_range: Dict[str, Any]) -> MetricValue:
    if not candidate_range or not job_range:
        return value(None, {"candidate": candidate_range, "job": job_range})
    c_min = safe_float(candidate_range.get("min"), safe_float(candidate_range.get("target")))
    c_max = safe_float(candidate_range.get("max"), c_min)
    j_min = safe_float(job_range.get("min"), safe_float(job_range.get("target")))
    j_max = safe_float(job_range.get("max"), j_min)
    if None in (c_min, c_max, j_min, j_max):
        return value(None, {"candidate": candidate_range, "job": job_range})
    intersection_low = max(c_min, j_min)
    intersection_high = min(c_max, j_max)
    overlap = max(0.0, intersection_high - intersection_low)
    if overlap > 0 or (c_min == c_max == j_min == j_max):
        return value(1.0, {"candidate": candidate_range, "job": job_range})
    if intersection_low == intersection_high:
        return value(0.8, {"candidate": candidate_range, "job": job_range, "boundary_touch": True})
    gap = min(abs(c_min - j_max), abs(j_min - c_max))
    scale = max(c_max, j_max, 1.0)
    return value(clamp(1.0 - gap / scale), {"candidate": candidate_range, "job": job_range})


LEVELS = {"low": 1, "低": 1, "medium": 2, "中": 2, "high": 3, "高": 3}
FREQUENCY = {"monthly": 1, "每月": 1, "biweekly": 2, "双周": 2, "weekly": 3, "每周": 3, "continuous": 4, "持续": 4}
CLARITY = {"unclear": 1, "不清晰": 1, "basic": 2, "基本": 2, "clear": 3, "清晰": 3, "transparent": 4, "透明": 4}


METRIC_FUNCTIONS: Dict[str, MetricFunction] = {
    "required_skill_coverage": lambda c: _weighted_skill_part(c.required_rows, "coverage_score"),
    "preferred_skill_coverage": lambda c: _weighted_skill_part(c.preferred_rows, "coverage_score"),
    "skill_proficiency": lambda c: _skill_evidence(c, "level_score"),
    "skill_experience_years": lambda c: _skill_evidence(c, "years_score"),
    "skill_recency": lambda c: _skill_evidence(c, "recency_score"),
    "evidence_strength": lambda c: _skill_evidence(c, "evidence_score"),
    "quantified_impact": lambda c: _skill_evidence(c, "impact_score"),
    "responsibility_overlap": _responsibility,
    "total_experience": _experience,
    "industry_experience": _industry,
    "seniority_alignment": lambda c: _ordered_fit(c.candidate.get("current_seniority"), c.job.get("seniority"), {"intern": 1, "实习": 1, "junior": 2, "初级": 2, "mid": 3, "中级": 3, "senior": 4, "高级": 4, "lead": 5, "负责人": 5, "manager": 6, "经理": 6, "director": 7, "总监": 7}),
    "project_complexity": lambda c: _numeric_requirement(c, "project_complexity", "project_complexity_required"),
    "education_fit": _education,
    "certification_fit": lambda c: _named_qualification(c.candidate.get("certifications", []), c.job.get("certifications", [])),
    "language_fit": lambda c: _named_qualification(c.candidate.get("languages", []), c.job.get("languages", [])),
    "leadership_experience": lambda c: _numeric_requirement(c, "leadership_years", "leadership_required_years"),
    "collaboration_evidence": _collaboration,
    "location_feasibility": lambda c: _overlap(c.candidate.get("preferred_locations", []), [c.job.get("location")] if c.job.get("location") else []),
    "work_mode_feasibility": lambda c: _overlap(c.candidate.get("preferred_work_modes", []), c.job.get("work_modes", [])),
    "employment_type_feasibility": lambda c: _overlap(c.candidate.get("employment_types", []), [c.job.get("employment_type")] if c.job.get("employment_type") else []),
    "availability_feasibility": _availability,
    "skill_breadth": _skill_breadth,
    "core_skill_depth": _core_skill_depth,
    "transferable_skill_readiness": _transferable_readiness,
    "toolchain_compatibility": lambda c: _overlap(c.candidate.get("toolchains", []), c.job.get("toolchains", [])),
    "domain_knowledge": lambda c: _overlap(c.candidate.get("domain_knowledge", []), c.job.get("domain_knowledge", [])),
    "achievement_consistency": _achievement_consistency,
    "evidence_recency": _evidence_recency,
    "outcome_relevance": _outcome_relevance,
    "ownership_evidence": lambda c: _text_evidence_fit(c, "ownership_evidence", "ownership_expectations"),
    "problem_solving_evidence": lambda c: _text_evidence_fit(c, "problem_solving_evidence", "problem_solving_expectations"),
    "communication_evidence": lambda c: _text_evidence_fit(c, "communication_evidence", "communication_expectations"),
    "stakeholder_management": lambda c: _text_evidence_fit(c, "stakeholder_evidence", "stakeholder_expectations"),
    "delivery_reliability": lambda c: _text_evidence_fit(c, "delivery_evidence", "delivery_expectations"),
    "innovation_evidence": lambda c: _text_evidence_fit(c, "innovation_evidence", "innovation_expectations"),
    "risk_management_evidence": lambda c: _text_evidence_fit(c, "risk_management_evidence", "risk_management_expectations"),
    "learning_agility": lambda c: _text_evidence_fit(c, "learning_evidence", "learning_agility_expectations"),
    "adaptability_evidence": lambda c: _text_evidence_fit(c, "adaptability_evidence", "adaptability_expectations"),
    "decision_quality_evidence": lambda c: _text_evidence_fit(c, "decision_evidence", "decision_quality_expectations"),
    "analytical_thinking": lambda c: _text_evidence_fit(c, "analytical_evidence", "analytical_expectations"),
    "customer_orientation": lambda c: _text_evidence_fit(c, "customer_evidence", "customer_orientation_expectations"),
    "compliance_awareness": lambda c: _text_evidence_fit(c, "compliance_evidence", "compliance_expectations"),
    "target_role_alignment": _role,
    "growth_goal_alignment": lambda c: _overlap(c.candidate.get("growth_goals", []), c.job.get("growth_offerings", [])),
    "learning_opportunity_alignment": lambda c: _overlap(c.candidate.get("learning_goals", []), c.job.get("learning_offerings", [])),
    "compensation_alignment": _salary,
    "location_preference_alignment": lambda c: _overlap(c.candidate.get("preferred_locations", []), [c.job.get("location")] if c.job.get("location") else []),
    "work_mode_preference_alignment": lambda c: _overlap(c.candidate.get("preferred_work_modes", []), c.job.get("work_modes", [])),
    "employment_type_preference": lambda c: _overlap(c.candidate.get("employment_types", []), [c.job.get("employment_type")] if c.job.get("employment_type") else []),
    "start_date_alignment": _availability,
    "values_alignment": lambda c: _overlap(c.candidate.get("values", []), c.job.get("values", [])),
    "industry_interest_alignment": lambda c: _overlap(c.candidate.get("industry_interests", []), c.job.get("industries", [])),
    "seniority_preference_alignment": _candidate_seniority,
    "workload_preference_alignment": lambda c: _preference_order(c, "preferred_workload", "workload", {"light": 1, "轻": 1, "standard": 2, "标准": 2, "intensive": 3, "高强度": 3}, True),
    "travel_preference_alignment": lambda c: _preference_order(c, "travel_preference", "travel_requirement", {"none": 0, "无": 0, "occasional": 1, "偶尔": 1, "frequent": 2, "频繁": 2}, True),
    "team_culture_alignment": lambda c: _overlap(c.candidate.get("team_culture_preferences", []), c.job.get("team_culture", [])),
    "role_stability_alignment": lambda c: _preference_order(c, "role_stability_preference", "role_stability", {"flexible": 1, "灵活": 1, "stable": 2, "稳定": 2, "long-term": 3, "长期": 3}),
    "benefits_alignment": lambda c: _overlap(c.candidate.get("benefit_preferences", []), c.job.get("benefits", [])),
    "manager_style_alignment": lambda c: _overlap(c.candidate.get("manager_style_preferences", []), c.job.get("manager_style", [])),
    "career_path_alignment": lambda c: _overlap(c.candidate.get("career_path_goals", []), c.job.get("career_paths", [])),
    "role_mission_alignment": lambda c: _overlap(c.candidate.get("role_mission_preferences", []), c.job.get("role_mission", [])),
    "daily_task_interest": lambda c: _overlap(c.candidate.get("daily_task_interests", []), c.job.get("daily_tasks", [])),
    "autonomy_preference_alignment": lambda c: _preference_order(c, "autonomy_preference", "autonomy_level", LEVELS),
    "feedback_frequency_alignment": lambda c: _preference_order(c, "feedback_frequency_preference", "feedback_frequency", FREQUENCY),
    "collaboration_style_alignment": lambda c: _overlap(c.candidate.get("collaboration_style_preferences", []), c.job.get("collaboration_style", [])),
    "decision_style_alignment": lambda c: _overlap(c.candidate.get("decision_style_preferences", []), c.job.get("decision_style", [])),
    "pace_preference_alignment": lambda c: _preference_order(c, "pace_preference", "pace", LEVELS, True),
    "innovation_environment_alignment": lambda c: _overlap(c.candidate.get("innovation_environment_preferences", []), c.job.get("innovation_environment", [])),
    "learning_budget_alignment": lambda c: _minimum_offering(c, "learning_budget_expectation", "learning_budget"),
    "mentorship_access_alignment": lambda c: _overlap(c.candidate.get("mentorship_preferences", []), c.job.get("mentorship", [])),
    "promotion_clarity_alignment": lambda c: _preference_order(c, "promotion_clarity_preference", "promotion_clarity", CLARITY),
    "compensation_structure_alignment": lambda c: _overlap(c.candidate.get("compensation_structure_preferences", []), c.job.get("compensation_structure", [])),
    "bonus_expectation_alignment": lambda c: _range_fit(c.candidate.get("bonus_expectation", {}), c.job.get("bonus_range", {})),
    "annual_leave_alignment": lambda c: _minimum_offering(c, "min_annual_leave_days", "annual_leave_days"),
    "schedule_flexibility_alignment": lambda c: _overlap(c.candidate.get("schedule_flexibility_preferences", []), c.job.get("schedule_flexibility", [])),
    "commute_feasibility": lambda c: _maximum_burden(c, "max_commute_minutes", "commute_minutes"),
    "travel_burden_alignment": lambda c: _maximum_burden(c, "max_travel_days_per_month", "travel_days_per_month"),
    "job_security_alignment": lambda c: _preference_order(c, "job_security_preference", "job_security", LEVELS),
    "purpose_alignment": lambda c: _overlap(c.candidate.get("purpose_preferences", []), c.job.get("purpose", [])),
    "psychological_safety_alignment": lambda c: _overlap(c.candidate.get("psychological_safety_preferences", []), c.job.get("psychological_safety", [])),
}


def evaluate_metric(indicator_id: str, context: MetricContext) -> MetricValue:
    function = METRIC_FUNCTIONS.get(indicator_id)
    if function is None:
        raise KeyError(f"未实现的指标ID：{indicator_id}")
    return function(context)
