"""本模块提供可复用的离线评测、排序指标、人工标注一致性和消融比较方法。"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

from .engine import match_pair
from .ontology import canonicalize
from .parser import parse_candidate, parse_job
from .text import weighted_overlap


EVALUATION_MODES = ("keyword", "skill_experience", "recruiter_only", "full")


def _keyword_score(candidate: Dict[str, Any], job: Dict[str, Any]) -> float:
    candidate_text = " ".join([str(candidate.get("summary", "")), str(candidate.get("source_text", "")), *[str(item.get("name", "")) for item in candidate.get("skills", [])]])
    job_text = " ".join([str(job.get("title", "")), str(job.get("summary", "")), str(job.get("source_text", "")), *[str(item.get("name", "")) for item in job.get("required_skills", [])]])
    return round(min(100.0, weighted_overlap(candidate_text, job_text) * 100), 2)


def _skill_experience_score(candidate: Dict[str, Any], job: Dict[str, Any]) -> float:
    candidate_skills = {canonicalize(item.get("name", "")) for item in candidate.get("skills", [])}
    required = {canonicalize(item.get("name", "")) for item in job.get("required_skills", [])}
    coverage = len(candidate_skills & required) / len(required) if required else 0.5
    actual, minimum = candidate.get("experience_years"), job.get("min_experience_years")
    experience = 0.5 if actual is None or minimum is None else min(1.0, float(actual) / max(float(minimum), 0.5))
    return round((0.75 * coverage + 0.25 * experience) * 100, 2)


def score_for_mode(candidate_input: Any, job_input: Any, mode: str, config: Dict[str, Any] | None = None) -> float:
    """用指定消融模式给单个候选人—岗位对打分。"""
    if mode not in EVALUATION_MODES:
        raise ValueError("未知评测模式：" + mode)
    candidate, job = parse_candidate(candidate_input), parse_job(job_input)
    if mode == "keyword":
        return _keyword_score(candidate, job)
    if mode == "skill_experience":
        return _skill_experience_score(candidate, job)
    result = match_pair(candidate, job, config=config)
    scores = result.get("scores", {})
    if mode == "recruiter_only":
        return float(scores.get("provisional_recruiter") or 0.0)
    if scores.get("overall") is not None:
        return float(scores["overall"])
    if scores.get("status") == "hard_failure":
        return 0.0
    raise ValueError("full模式需要候选人偏好与岗位条件足以形成双向正式分；请先补齐评测数据")


def _ndcg(relevances: List[float], k: int) -> float:
    def dcg(values: List[float]) -> float:
        return sum((2 ** value - 1) / math.log2(index + 2) for index, value in enumerate(values[:k]))
    ideal = dcg(sorted(relevances, reverse=True))
    return 0.0 if ideal == 0 else dcg(relevances) / ideal


def _pairwise_consistency(ranked: List[str], relevance: Dict[str, float]) -> float | None:
    comparable, agreed = 0, 0
    positions = {job_id: index for index, job_id in enumerate(ranked)}
    ids = list(positions)
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            if relevance.get(left, 0) == relevance.get(right, 0):
                continue
            comparable += 1
            expected_left = relevance.get(left, 0) > relevance.get(right, 0)
            actual_left = positions[left] < positions[right]
            agreed += int(expected_left == actual_left)
    return agreed / comparable if comparable else None


def evaluate_records(records: Iterable[Dict[str, Any]], mode: str, config: Dict[str, Any] | None = None, k: int = 3) -> Dict[str, Any]:
    """评估JSONL记录，失败样本计入失败率而不会中止整个数据集。"""
    query_results, failures = [], []
    decision_hits, decision_total, invariance_deltas = 0, 0, []
    for record in records:
        query_id = str(record.get("query_id") or f"query-{len(query_results) + len(failures) + 1}")
        try:
            candidate = record["candidate"]
            jobs = record["jobs"]
            relevance = {str(key): float(value) for key, value in record.get("relevance", {}).items()}
            scored = []
            for job in jobs:
                job_id = str(job.get("id") or f"job-{len(scored) + 1}")
                scored.append((job_id, score_for_mode(candidate, job, mode, config)))
            scored.sort(key=lambda item: (-item[1], item[0]))
            ranked = [job_id for job_id, _ in scored]
            ranked_relevance = [relevance.get(job_id, 0.0) for job_id in ranked]
            relevant_ids = {job_id for job_id, value in relevance.items() if value > 0}
            top_hit = bool(set(ranked[:k]) & relevant_ids)
            consistency = _pairwise_consistency(ranked, relevance)

            reviews = record.get("human_reviews", [])
            if reviews:
                labels = [str(item.get("recommended_job_id", "")) for item in reviews if item.get("recommended_job_id")]
                if labels:
                    majority = max(set(labels), key=labels.count)
                    decision_total += 1
                    decision_hits += int(ranked[0] == majority)

            for variant in record.get("protected_variants", []):
                variant_scores = [score_for_mode(variant, job, mode, config) for job in jobs]
                base_scores = dict(scored)
                for job, variant_score in zip(jobs, variant_scores):
                    invariance_deltas.append(abs(variant_score - base_scores[str(job.get("id"))]))

            query_results.append({
                "query_id": query_id,
                "ranking": [{"job_id": job_id, "score": score} for job_id, score in scored],
                f"hit_at_{k}": top_hit,
                f"ndcg_at_{k}": round(_ndcg(ranked_relevance, k), 4),
                "rank_consistency": None if consistency is None else round(consistency, 4),
            })
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"query_id": query_id, "error": str(exc)})
    total = len(query_results) + len(failures)
    consistency_values = [row["rank_consistency"] for row in query_results if row["rank_consistency"] is not None]
    return {
        "mode": mode,
        "dataset_records": total,
        "successful_records": len(query_results),
        "failure_count": len(failures),
        "failure_handling_rate": round(len(query_results) / total, 4) if total else 0.0,
        f"top_{k}_hit_rate": round(sum(row[f"hit_at_{k}"] for row in query_results) / len(query_results), 4) if query_results else 0.0,
        f"mean_ndcg_at_{k}": round(sum(row[f"ndcg_at_{k}"] for row in query_results) / len(query_results), 4) if query_results else 0.0,
        "mean_rank_consistency": round(sum(consistency_values) / len(consistency_values), 4) if consistency_values else None,
        "human_review_decision_consistency": round(decision_hits / decision_total, 4) if decision_total else None,
        "protected_attribute_max_score_delta": round(max(invariance_deltas), 4) if invariance_deltas else None,
        "protected_attribute_mean_score_delta": round(sum(invariance_deltas) / len(invariance_deltas), 4) if invariance_deltas else None,
        "queries": query_results,
        "failures": failures,
    }
