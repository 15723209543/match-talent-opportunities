"""本模块编排批量候选人、岗位和多对多匹配，并将不可比较结果分流。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .constants import MAX_BATCH_ITEMS, MAX_MATRIX_PAIRS
from .engine import match_pair
from .excel_config import load_metric_config


def _bounded(values: Iterable[Any], label: str) -> List[Any]:
    """把迭代器转为列表并限制单次请求规模。"""
    items = list(values)
    if len(items) > MAX_BATCH_ITEMS:
        raise ValueError(f"{label}数量不能超过{MAX_BATCH_ITEMS}")
    return items


def _ranking_row(result: Dict[str, Any], entity_key: str, fallback: str) -> Dict[str, Any]:
    scores = result["scores"]
    return {
        "rank": None,
        entity_key: result["meta"].get(entity_key) or fallback,
        "status": scores["status"],
        "rank_eligible": scores["status"] == "ready_for_review",
        "overall": scores["overall"],
        "recruiter": scores["recruiter"],
        "candidate": scores["candidate"],
        "confidence": result["confidence"]["score"],
        "band": scores["band"],
        "hard_failures": sum(gate.get("status") == "fail" for gate in result.get("gates", [])),
        "data_sufficiency": scores["data_sufficiency"],
        "verified_gaps": result.get("recommendations", {}).get("verified_gaps", []),
        "evidence_needed": result.get("recommendations", {}).get("evidence_needed", []),
    }


def _triage(rows: List[Dict[str, Any]], entity_key: str) -> Dict[str, Any]:
    ready = [row for row in rows if row["status"] == "ready_for_review"]
    needs_data = [row for row in rows if row["status"] == "insufficient_data"]
    unverified_hard = [row for row in rows if row["status"] == "hard_requirement_unverified"]
    hard_failures = [row for row in rows if row["status"] == "hard_failure"]
    ready.sort(key=lambda row: (-float(row["overall"]), -float(row["confidence"]), str(row[entity_key])))
    needs_data.sort(key=lambda row: (-float(row["confidence"]), str(row[entity_key])))
    unverified_hard.sort(key=lambda row: (-float(row["confidence"]), str(row[entity_key])))
    hard_failures.sort(key=lambda row: (-float(row["confidence"]), str(row[entity_key])))
    for rank, row in enumerate(ready, 1):
        row["rank"] = rank
    return {
        "ready_for_review": ready,
        "needs_more_data": needs_data,
        "unverified_hard_requirements": unverified_hard,
        "hard_failures": hard_failures,
        "counts": {
            "ready_for_review": len(ready),
            "needs_more_data": len(needs_data),
            "unverified_hard_requirements": len(unverified_hard),
            "hard_failures": len(hard_failures),
        },
        "notice": "仅ready_for_review参与正式排序；未知硬条件、资料不足和明确硬失败分别处理。",
    }


def triage_candidates(candidates: Iterable[Any], job: Any, weights_path: str | None = None, profile: str = "general", as_of_date: Any = None) -> Dict[str, Any]:
    """为一个岗位匹配候选人；同一批次只读取一次Excel配置。"""
    candidate_list = _bounded(candidates, "候选人")
    config = load_metric_config(weights_path, profile)
    rows = [
        _ranking_row(match_pair(candidate, job, config=config, as_of_date=as_of_date), "candidate_id", f"candidate-{index}")
        for index, candidate in enumerate(candidate_list, 1)
    ]
    return _triage(rows, "candidate_id")


def triage_jobs(candidate: Any, jobs: Iterable[Any], weights_path: str | None = None, profile: str = "general", as_of_date: Any = None) -> Dict[str, Any]:
    """为一名候选人匹配岗位；同一批次只读取一次Excel配置。"""
    job_list = _bounded(jobs, "岗位")
    config = load_metric_config(weights_path, profile)
    rows = [
        _ranking_row(match_pair(candidate, job, config=config, as_of_date=as_of_date), "job_id", f"job-{index}")
        for index, job in enumerate(job_list, 1)
    ]
    return _triage(rows, "job_id")


def rank_candidates(candidates: Iterable[Any], job: Any, weights_path: str | None = None, profile: str = "general") -> List[Dict[str, Any]]:
    """兼容旧接口，仅返回具备正式比较条件的候选人。"""
    return triage_candidates(candidates, job, weights_path, profile)["ready_for_review"]


def rank_jobs(candidate: Any, jobs: Iterable[Any], weights_path: str | None = None, profile: str = "general") -> List[Dict[str, Any]]:
    """兼容旧接口，仅返回具备正式比较条件的岗位。"""
    return triage_jobs(candidate, jobs, weights_path, profile)["ready_for_review"]


def match_matrix(candidates: Iterable[Any], jobs: Iterable[Any], weights_path: str | None = None, profile: str = "general") -> Dict[str, Any]:
    """执行多对多匹配并标注每一对是否可进入正式比较。"""
    candidate_list = _bounded(candidates, "候选人")
    job_list = _bounded(jobs, "岗位")
    if len(candidate_list) * len(job_list) > MAX_MATRIX_PAIRS:
        raise ValueError(f"多对多匹配数量不能超过{MAX_MATRIX_PAIRS}对")
    config = load_metric_config(weights_path, profile)
    rows = []
    for candidate in candidate_list:
        for job in job_list:
            result = match_pair(candidate, job, config=config)
            scores = result["scores"]
            rows.append({
                "candidate_id": result["meta"]["candidate_id"],
                "job_id": result["meta"]["job_id"],
                "status": scores["status"],
                "overall": scores["overall"],
                "recruiter": scores["recruiter"],
                "candidate": scores["candidate"],
                "confidence": result["confidence"]["score"],
                "hard_failures": sum(gate.get("status") == "fail" for gate in result.get("gates", [])),
            })
    return {
        "candidate_count": len(candidate_list),
        "job_count": len(job_list),
        "pair_count": len(rows),
        "matches": rows,
        "notice": "只有status为ready_for_review的配对可进入正式比较。",
    }
