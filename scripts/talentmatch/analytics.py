"""本模块汇总类别得分、主要贡献、完整度、系数集中度和敏感性分析数据。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List

from .text import harmonic


def _known(dimensions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in dimensions if item.get("effective_score") is not None and item.get("coefficient", 0) > 0]


def _weighted_score(items: List[Dict[str, Any]]) -> float | None:
    denominator = sum(float(item.get("coefficient", 0)) for item in items)
    if denominator <= 0:
        return None
    numerator = sum(float(item["effective_score"]) * float(item.get("coefficient", 0)) for item in items)
    return round(numerator / denominator, 2)


def _category_summary(dimensions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in dimensions:
        groups[str(item.get("category") or "未分类")].append(item)
    total_coefficient = sum(float(item.get("coefficient", 0)) for item in _known(dimensions))
    rows = []
    for category, items in groups.items():
        known = _known(items)
        not_applicable = [item for item in items if item.get("status") == "not_applicable"]
        unknown = [item for item in items if item.get("effective_score") is None and item.get("status") != "not_applicable"]
        applicable_count = len(known) + len(unknown)
        coefficient = sum(float(item.get("coefficient", 0)) for item in known)
        raw_score = _weighted_score(known)
        known_rate = len(known) / applicable_count * 100 if applicable_count else 0.0
        minimum_known = min(2, applicable_count) if applicable_count else 0
        category_ready = bool(raw_score is not None and len(known) >= minimum_known and known_rate >= 50.0)
        category_status = "ready" if category_ready else "not_applicable" if not applicable_count else "insufficient_category_data"
        rows.append({
            "category": category,
            "score": raw_score,
            "display_score": raw_score if category_ready else None,
            "status": category_status,
            "metric_count": applicable_count,
            "configured_metric_count": len(items),
            "known_count": len(known),
            "unknown_count": len(unknown),
            "not_applicable_count": len(not_applicable),
            "known_rate": round(known_rate, 2),
            "minimum_known_metrics_for_display": minimum_known,
            "minimum_known_rate_for_display": 50.0,
            "coefficient_share": round(coefficient / total_coefficient * 100, 2) if total_coefficient else 0.0,
        })
    return sorted(rows, key=lambda row: (-1 if row["display_score"] is None else -row["display_score"], row["category"]))


def _compact_metric(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "side": item.get("side"),
        "category": item.get("category"),
        "score": item.get("score"),
        "coefficient": item.get("coefficient"),
        "contribution": item.get("contribution"),
        "status": item.get("status"),
    }


def _coefficient_concentration(dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    known = _known(dimensions)
    total = sum(float(item.get("coefficient", 0)) for item in known)
    shares = [float(item.get("coefficient", 0)) / total for item in known] if total else []
    hhi = sum(share * share for share in shares)
    effective_count = (1 / hhi) if hhi else 0.0
    return {
        "hhi": round(hhi, 4),
        "effective_metric_count": round(effective_count, 2),
        "level": "集中" if hhi >= 0.18 else "中等" if hhi >= 0.10 else "分散",
        "interpretation": "值越高，少数指标对结果的影响越集中。",
    }


def _sensitivity(result: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    base_scores = result.get("scores", {})
    base_recruiter = base_scores.get("provisional_recruiter")
    base_candidate = base_scores.get("provisional_candidate")
    base_overall = base_scores.get("provisional_overall")
    if base_recruiter is None or base_candidate is None or base_overall is None:
        return []
    overall_weights = result.get("method", {}).get("overall_coefficients", {})
    rows = []
    sides = {
        "recruiter": result.get("recruiter_dimensions", []),
        "candidate": result.get("candidate_dimensions", []),
    }
    for side, dimensions in sides.items():
        known = _known(dimensions)
        for changed in known:
            adjusted = []
            for item in known:
                clone = dict(item)
                if item.get("id") == changed.get("id"):
                    clone["coefficient"] = float(item.get("coefficient", 0)) * 1.2
                adjusted.append(clone)
            changed_side = _weighted_score(adjusted)
            recruiter = changed_side if side == "recruiter" else float(base_recruiter)
            candidate = changed_side if side == "candidate" else float(base_candidate)
            if changed_side is None:
                continue
            changed_overall = harmonic(
                [recruiter, candidate],
                [float(overall_weights.get("overall_recruiter", 1)), float(overall_weights.get("overall_candidate", 1))],
            )
            delta = round(changed_overall - float(base_overall), 2)
            rows.append({
                "id": changed.get("id"),
                "name": changed.get("name"),
                "side": side,
                "scenario": "该指标系数提高20%",
                "overall_delta": delta,
                "scenario_overall": round(changed_overall, 2),
            })
    return sorted(rows, key=lambda row: (-abs(row["overall_delta"]), row["id"]))[:limit]


def build_analytics(result: Dict[str, Any]) -> Dict[str, Any]:
    recruiter = result.get("recruiter_dimensions", [])
    candidate = result.get("candidate_dimensions", [])
    dimensions = recruiter + candidate
    known = _known(dimensions)
    unknown = [item for item in dimensions if item.get("effective_score") is None and item.get("status") != "not_applicable"]
    not_applicable = [item for item in dimensions if item.get("status") == "not_applicable"]
    contributions = sorted(known, key=lambda item: (-(item.get("contribution") or 0), item.get("id", "")))
    weakest = sorted(known, key=lambda item: (item.get("score", 101), -(item.get("coefficient") or 0)))
    high_weight_unknown = sorted(unknown, key=lambda item: (-(item.get("coefficient") or 0), item.get("id", "")))
    statuses = Counter(str(row.get("status") or "unknown") for row in result.get("evidence_matrix", []))
    evidence_total = sum(statuses.values())
    scores = result.get("scores", {})
    recruiter_value = scores.get("recruiter")
    candidate_value = scores.get("candidate")
    provisional = recruiter_value is None or candidate_value is None
    recruiter_score = scores.get("provisional_recruiter") if recruiter_value is None else recruiter_value
    candidate_score = scores.get("provisional_candidate") if candidate_value is None else candidate_value
    score_balance = {
        "recruiter": recruiter_score,
        "candidate": candidate_score,
        "absolute_gap": None,
        "lower_side": "not_available",
        "provisional": provisional,
        "interpretation": "双侧差距只用于发现不均衡，不代表录用结论；暂估值不能用于正式排序。",
    }
    if recruiter_score is not None and candidate_score is not None:
        recruiter_number, candidate_number = float(recruiter_score), float(candidate_score)
        score_balance.update({
            "recruiter": round(recruiter_number, 2),
            "candidate": round(candidate_number, 2),
            "absolute_gap": round(abs(recruiter_number - candidate_number), 2),
            "lower_side": "recruiter" if recruiter_number < candidate_number else "candidate" if candidate_number < recruiter_number else "balanced",
        })
    return {
        "score_balance": score_balance,
        "category_scores": {
            "recruiter": _category_summary(recruiter),
            "candidate": _category_summary(candidate),
        },
        "top_contribution_drivers": [_compact_metric(item) for item in contributions[:10]],
        "priority_verification_dimensions": [_compact_metric(item) for item in (high_weight_unknown + weakest)[:10]],
        "data_completeness": {
            "known_metrics": len(known),
            "unknown_metrics": len(unknown),
            "not_applicable_metrics": len(not_applicable),
            "total_metrics": len(dimensions),
            "known_rate": round(len(known) / (len(known) + len(unknown)) * 100, 2) if known or unknown else 0.0,
            "unknown_ids": [item.get("id") for item in unknown],
            "not_applicable_ids": [item.get("id") for item in not_applicable],
        },
        "evidence_coverage": {
            "total_rows": evidence_total,
            "status_counts": dict(sorted(statuses.items())),
            "supported_rate": round(sum(statuses[key] for key in ("exact", "supported", "met") if key in statuses) / evidence_total * 100, 2) if evidence_total else None,
        },
        "coefficient_concentration": {
            "recruiter": _coefficient_concentration(recruiter),
            "candidate": _coefficient_concentration(candidate),
        },
        "sensitivity_analysis": _sensitivity(result),
        "analysis_notice": "敏感性分析采用单指标系数提高20%的局部情景，不是因果推断；信息不足时只展示暂估分析，所有结论均需人工复核。",
    }
