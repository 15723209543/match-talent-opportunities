"""本模块为HR、求职者、面试官和人才管理脚本提供共用的命令行参数与动作分派。"""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any, Dict, Iterable, List

from .batch import triage_candidates, triage_jobs
from .engine import match_pair
from .fairness import audit_record, audit_text
from .io import InputError, load_collection, load_source, write_json
from .parser import parse_candidate
from .quality import audit_job
from .persona_reporting import build_persona_payload, write_persona_report


PAIR_ACTIONS = {
    "hr.match_candidate", "hr.screening_questions", "hr.salary_fit", "hr.decision_report",
    "candidate.match_job", "candidate.resume_gap", "candidate.resume_evidence",
    "candidate.interview_prep", "candidate.career_path", "candidate.learning_plan",
    "interviewer.question_plan", "interviewer.evidence_probe", "interviewer.scorecard",
    "interviewer.consistency_audit", "interviewer.feedback_summary",
    "talent_manager.development_plan", "talent_manager.succession_readiness",
    "talent_manager.retention_signals",
    "hr.analyze_capability", "hr.analyze_behavior", "hr.analyze_evidence_quality",
    "hr.analyze_culture_fit", "hr.analyze_work_constraints", "hr.analyze_risk_compliance",
    "hr.sensitivity_analysis", "hr.data_quality",
    "candidate.analyze_personality", "candidate.analyze_capability", "candidate.analyze_workstyle",
    "candidate.analyze_culture", "candidate.analyze_compensation", "candidate.analyze_schedule",
    "candidate.sensitivity_analysis", "candidate.data_quality", "candidate.full_report",
    "interviewer.capability_probe", "interviewer.workstyle_probe", "interviewer.risk_probe",
    "interviewer.full_report", "talent_manager.capability_matrix", "talent_manager.development_priorities",
}
RANK_CANDIDATE_ACTIONS = {"hr.rank_candidates", "hr.shortlist", "hr.compare_candidates", "talent_manager.training_priorities"}
RANK_JOB_ACTIONS = {"candidate.rank_jobs", "candidate.compare_offers", "talent_manager.internal_mobility"}
JOB_ACTIONS = {"hr.analyze_jd", "interviewer.bias_check"}
CANDIDATE_ACTIONS = {"talent_manager.skill_inventory"}


def _metric(result: Dict[str, Any], indicator_id: str) -> Dict[str, Any]:
    dimensions = result.get("recruiter_dimensions", []) + result.get("candidate_dimensions", [])
    return next((item for item in dimensions if item.get("id") == indicator_id), {})


def _top_metrics(result: Dict[str, Any], reverse: bool, limit: int = 5) -> List[Dict[str, Any]]:
    items = [
        {"id": item["id"], "name": item["name"], "score": item["score"], "coefficient": item["coefficient"], "status": item["status"]}
        for item in result.get("recruiter_dimensions", []) + result.get("candidate_dimensions", [])
        if item.get("score") is not None
    ]
    return sorted(items, key=lambda item: item["score"], reverse=reverse)[:limit]


def _pair_output(action: str, result: Dict[str, Any]) -> Dict[str, Any]:
    recommendations = result.get("recommendations", {})
    if action == "hr.match_candidate":
        return build_persona_payload(result, "hr")
    if action == "candidate.match_job":
        return build_persona_payload(result, "candidate")
    if action == "hr.screening_questions":
        return {"candidate_id": result["meta"]["candidate_id"], "job_id": result["meta"]["job_id"], "questions": recommendations.get("interview_questions", []), "needs_verification": recommendations.get("needs_verification", [])}
    if action == "hr.salary_fit":
        return {"scores": result["scores"], "compensation_alignment": _metric(result, "compensation_alignment"), "human_review_required": True}
    if action == "hr.decision_report":
        return {"scores": result["scores"], "confidence": result["confidence"], "summary": result["executive_summary"], "hard_gates": result["gates"], "top_strengths": _top_metrics(result, True), "top_risks": _top_metrics(result, False), "next_actions": recommendations.get("recruiter_actions", [])}
    if action in {"candidate.resume_gap", "candidate.learning_plan", "talent_manager.development_plan"}:
        return {"scores": result["scores"], "explicit_requirement_gaps": recommendations.get("explicit_requirement_gaps", []), "verified_gaps": recommendations.get("verified_gaps", []), "evidence_needed": recommendations.get("evidence_needed", []), "needs_verification": recommendations.get("needs_verification", []), "development_plan": recommendations.get("development_plan", {}), "resume_actions": recommendations.get("resume_actions", [])}
    if action == "candidate.resume_evidence":
        rows = [row for row in result.get("evidence_matrix", []) if row.get("type") in {"required_skill", "preferred_skill"}]
        return {"evidence_rows": rows, "strong_evidence": [row for row in rows if (row.get("evidence_score") or 0) >= 0.8], "weak_or_missing_evidence": [row for row in rows if row.get("evidence_score") is None or row.get("evidence_score", 0) < 0.6]}
    if action in {"candidate.interview_prep", "interviewer.question_plan"}:
        return {"summary": result["executive_summary"], "questions": recommendations.get("interview_questions", []), "hard_gates": result.get("gates", [])}
    if action == "candidate.career_path":
        ids = {"target_role_alignment", "growth_goal_alignment", "learning_opportunity_alignment", "seniority_preference_alignment", "career_path_alignment"}
        return {"career_metrics": [item for item in result.get("candidate_dimensions", []) if item.get("id") in ids], "development_plan": recommendations.get("development_plan", {})}
    if action == "interviewer.evidence_probe":
        unresolved = [row for row in result.get("evidence_matrix", []) if row.get("status") in {"missing", "partial", "unverified"}]
        return {"unresolved_evidence": unresolved, "probe_questions": recommendations.get("interview_questions", [])}
    if action == "interviewer.scorecard":
        return {"candidate_id": result["meta"]["candidate_id"], "job_id": result["meta"]["job_id"], "pre_interview_scores": result["scores"], "criteria": [{"indicator_id": item["id"], "indicator": item["name"], "excel_coefficient": item["coefficient"], "pre_score": item["score"], "interviewer_score_0_100": None, "evidence_note": ""} for item in result.get("recruiter_dimensions", [])], "decision_notice": "不得仅凭自动分数作出录用或淘汰决定"}
    if action == "interviewer.consistency_audit":
        dimensions = result.get("recruiter_dimensions", []) + result.get("candidate_dimensions", [])
        contribution_sum = round(sum(item.get("contribution") or 0 for item in dimensions), 2)
        return {"score_precision": result["scores"].get("precision"), "workbook_sha256": result["method"].get("indicator_workbook_sha256"), "indicator_count": result["method"].get("indicator_count"), "dimension_count": len(dimensions), "contribution_sum_both_sides": contribution_sum, "excel_read_policy": result["method"].get("coefficient_policy")}
    if action == "interviewer.feedback_summary":
        return {"summary": result["executive_summary"], "strengths": _top_metrics(result, True), "risks": _top_metrics(result, False), "verified_gaps": recommendations.get("verified_gaps", []), "needs_verification": recommendations.get("needs_verification", []), "human_review_required": True}
    if action == "talent_manager.succession_readiness":
        ids = {"required_skill_coverage", "skill_proficiency", "responsibility_overlap", "leadership_experience", "seniority_alignment"}
        return {"readiness_scores": result["scores"], "readiness_metrics": [item for item in result.get("recruiter_dimensions", []) if item.get("id") in ids], "gaps": recommendations.get("verified_gaps", []), "human_review_required": True}
    if action == "talent_manager.retention_signals":
        weak_preferences = [item for item in result.get("candidate_dimensions", []) if item.get("score") is not None and item["score"] < 60]
        return {"preference_misalignment_signals": weak_preferences, "scope_notice": "仅呈现岗位偏好不一致，不预测个人离职，不使用受保护属性", "human_review_required": True}
    category_actions = {
        "hr.analyze_capability": ("recruiter", {"技能能力", "岗位履历", "资格条件"}, "能力与履历核验"),
        "hr.analyze_behavior": ("recruiter", {"行为能力", "协作领导", "发展潜力"}, "行为能力证据"),
        "hr.analyze_evidence_quality": ("recruiter", {"证据成果"}, "成果与证据质量"),
        "hr.analyze_culture_fit": ("candidate", {"文化价值", "工作体验"}, "候选人体验与文化偏好"),
        "hr.analyze_work_constraints": ("recruiter", {"工作约束"}, "到岗与工作约束"),
        "hr.analyze_risk_compliance": ("recruiter", {"风险合规"}, "风险与合规证据"),
        "candidate.analyze_personality": ("candidate", {"工作体验", "文化价值"}, "工作风格与环境偏好（非心理测评）"),
        "candidate.analyze_capability": ("recruiter", {"技能能力", "岗位履历", "发展潜力"}, "岗位能力与可发展性"),
        "candidate.analyze_workstyle": ("candidate", {"工作体验", "工作安排"}, "工作方式与节奏"),
        "candidate.analyze_culture": ("candidate", {"文化价值"}, "文化、价值与心理安全"),
        "candidate.analyze_compensation": ("candidate", {"回报福利"}, "薪酬、奖金与福利"),
        "candidate.analyze_schedule": ("candidate", {"工作安排"}, "通勤、工时与出差安排"),
        "interviewer.capability_probe": ("recruiter", {"技能能力", "岗位履历", "行为能力"}, "面试能力追问"),
        "interviewer.workstyle_probe": ("candidate", {"工作体验", "文化价值"}, "双向工作风格追问"),
        "interviewer.risk_probe": ("recruiter", {"风险合规", "证据成果"}, "风险与证据追问"),
        "talent_manager.capability_matrix": ("recruiter", {"技能能力", "行为能力", "发展潜力"}, "内部人才能力矩阵"),
        "talent_manager.development_priorities": ("recruiter", {"技能能力", "发展潜力"}, "发展优先级"),
    }
    if action in category_actions:
        side, categories, title = category_actions[action]
        dimensions = result.get(f"{side}_dimensions", [])
        selected = [item for item in dimensions if item.get("category") in categories]
        output = {
            "analysis": title,
            "scores": result.get("scores", {}),
            "categories": [row for row in result.get("analytics", {}).get("category_scores", {}).get(side, []) if row.get("category") in categories],
            "metrics": selected,
            "unknown_metric_ids": [item.get("id") for item in selected if item.get("score") is None],
            "human_review_required": True,
        }
        if action == "candidate.analyze_personality":
            output["scope_notice"] = "只分析本人主动提供的工作风格偏好，不诊断人格、心理或健康状况。"
        if action.startswith("interviewer."):
            output["probe_questions"] = recommendations.get("interview_questions", [])
        return output
    if action in {"hr.sensitivity_analysis", "candidate.sensitivity_analysis"}:
        return {"scores": result.get("scores", {}), "sensitivity_analysis": result.get("analytics", {}).get("sensitivity_analysis", []), "notice": result.get("analytics", {}).get("analysis_notice"), "human_review_required": True}
    if action in {"hr.data_quality", "candidate.data_quality"}:
        return {"confidence": result.get("confidence", {}), "data_completeness": result.get("analytics", {}).get("data_completeness", {}), "evidence_coverage": result.get("analytics", {}).get("evidence_coverage", {}), "warnings": result.get("warnings", []), "next_step": "先补齐unknown指标所需字段，再比较分数。"}
    if action in {"candidate.full_report", "interviewer.full_report"}:
        persona = "candidate" if action.startswith("candidate.") else "interviewer"
        return build_persona_payload(result, persona)
    raise ValueError(f"未知双输入动作：{action}")


def _rank_candidate_output(action: str, candidates: List[Any], job: Any, metrics: str | None, top: int, profile: str, as_of_date: str | None = None) -> Dict[str, Any]:
    triage = triage_candidates(candidates, job, metrics, profile, as_of_date)
    ranking = triage["ready_for_review"]
    if action == "hr.rank_candidates":
        return triage
    if action == "hr.shortlist":
        review_queue = [item for item in ranking if item["overall"] >= 65][:top]
        return {"manual_review_queue": review_queue, "queue_count": len(review_queue), "criteria": {"minimum_formal_overall": 65, "status": "ready_for_review"}, "needs_more_data": triage["needs_more_data"], "unverified_hard_requirements": triage["unverified_hard_requirements"], "hard_failures": triage["hard_failures"], "notice": "此动作只建立人工复核队列，不代表自动推荐或录用。", "human_review_required": True}
    if action == "hr.compare_candidates":
        return {"comparison": ranking[:top], "needs_more_data": triage["needs_more_data"], "unverified_hard_requirements": triage["unverified_hard_requirements"], "hard_failures": triage["hard_failures"], "ranking_rule": "只有资料充分且所有硬条件已核验的结果进入正式排序", "human_review_required": True}
    gap_counter: Counter[str] = Counter()
    for candidate in candidates:
        result = match_pair(candidate, job, metrics, profile=profile, as_of_date=as_of_date)
        gap_counter.update(result.get("recommendations", {}).get("explicit_requirement_gaps", []))
    return {"training_priorities": [{"skill": name, "affected_people": count} for name, count in gap_counter.most_common()], "people_count": len(candidates), "notice": "仅用于制定群体培训主题，不用于个体惩罚性决策"}


def _rank_job_output(action: str, candidate: Any, jobs: List[Any], metrics: str | None, top: int, profile: str, as_of_date: str | None = None) -> Dict[str, Any]:
    triage = triage_jobs(candidate, jobs, metrics, profile, as_of_date)
    ranking = triage["ready_for_review"]
    label = "internal_opportunities" if action == "talent_manager.internal_mobility" else "offers" if action == "candidate.compare_offers" else "ranking"
    return {label: ranking[:top], "needs_more_data": triage["needs_more_data"], "unverified_hard_requirements": triage["unverified_hard_requirements"], "hard_failures": triage["hard_failures"], "human_review_required": True}


def _candidate_output(candidate: Any) -> Dict[str, Any]:
    parsed = parse_candidate(candidate)
    skills = parsed.get("skills", [])
    return {"candidate_id": parsed.get("id"), "skill_count": len(skills), "skills": [{"name": item.get("name"), "years": item.get("years"), "level": item.get("level"), "last_used_year": item.get("last_used_year"), "has_evidence": bool(item.get("evidence"))} for item in skills], "industries": parsed.get("industries", []), "leadership_years": parsed.get("leadership_years"), "notice": "技能盘点依据输入证据生成，未知项不作负面推断"}


def run_action(action: str) -> int:
    parser = argparse.ArgumentParser(description=f"TalentLens 中文场景脚本：{action}")
    parser.add_argument("--metrics", "--weights", dest="metrics", help="自定义匹配指标 Excel")
    parser.add_argument("--profile", choices=["general", "software_engineering", "product_operations", "sales_customer"], default="general", help="岗位权重模板")
    parser.add_argument("--as-of-date", help="评分基准日，格式YYYY-MM-DD；用于结果复现")
    parser.add_argument("--output", help="输出 JSON；省略时输出到控制台")
    parser.add_argument("--format", choices=["auto", "json", "markdown", "html", "text"], default="auto", help="输出格式；auto根据扩展名判断")
    parser.add_argument("--charts-dir", help="报告SVG图表目录；默认与报告同目录下的 *_assets")
    parser.add_argument("--top", type=int, default=10, help="最多返回多少条结果")
    if action in PAIR_ACTIONS:
        parser.add_argument("--candidate", required=True, help="候选人 JSON/TXT/DOCX")
        parser.add_argument("--job", required=True, help="岗位 JSON/TXT/DOCX")
    elif action in RANK_CANDIDATE_ACTIONS:
        parser.add_argument("--candidates", required=True, help="候选人目录或集合文件")
        parser.add_argument("--job", required=True, help="岗位文件")
    elif action in RANK_JOB_ACTIONS:
        parser.add_argument("--candidate", required=True, help="候选人文件")
        parser.add_argument("--jobs", required=True, help="岗位目录或集合文件")
    elif action in JOB_ACTIONS:
        parser.add_argument("--job", required=True, help="岗位文件")
    elif action in CANDIDATE_ACTIONS:
        parser.add_argument("--candidate", required=True, help="候选人文件")
    else:
        raise ValueError(f"未注册的场景动作：{action}")

    args = parser.parse_args()
    try:
        raw_result = None
        if action in PAIR_ACTIONS:
            raw_result = match_pair(load_source(args.candidate), load_source(args.job), args.metrics, profile=args.profile, as_of_date=args.as_of_date)
            output = _pair_output(action, raw_result)
        elif action in RANK_CANDIDATE_ACTIONS:
            candidates, job = load_collection(args.candidates), load_source(args.job)
            output = _rank_candidate_output(action, candidates, job, args.metrics, max(1, args.top), args.profile, args.as_of_date)
        elif action in RANK_JOB_ACTIONS:
            output = _rank_job_output(action, load_source(args.candidate), load_collection(args.jobs), args.metrics, max(1, args.top), args.profile, args.as_of_date)
        elif action == "hr.analyze_jd":
            output = audit_job(load_source(args.job))
        elif action == "interviewer.bias_check":
            job = load_source(args.job)
            output = {"fairness_audit": audit_text(job) if isinstance(job, str) else audit_record(job), "notice": "仅标记风险词，需由合规人员结合语境复核"}
        else:
            output = _candidate_output(load_source(args.candidate))
        inferred_format = args.format
        if inferred_format == "auto" and args.output:
            suffix = str(args.output).lower()
            inferred_format = "markdown" if suffix.endswith(".md") else "html" if suffix.endswith((".html", ".htm")) else "text" if suffix.endswith(".txt") else "json"
        elif inferred_format == "auto":
            inferred_format = "json"
        if inferred_format != "json":
            if raw_result is None:
                raise ValueError("Markdown/HTML/文本报告仅适用于需要候选人与岗位双输入的动作")
            if not args.output:
                raise ValueError("生成图文报告时必须指定 --output")
            persona = "candidate" if action.startswith("candidate.") else "hr" if action.startswith("hr.") else "interviewer" if action.startswith("interviewer.") else "talent_manager"
            write_persona_report(raw_result, persona, args.output, inferred_format, args.charts_dir)
        else:
            write_json(output, args.output)
        return 0
    except (InputError, ValueError, OSError) as exc:
        parser.error(str(exc))
        return 2
