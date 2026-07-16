"""本模块把明确差距、待核实证据和未知信息分别转成面试、简历与发展建议。"""

from __future__ import annotations

from typing import Any, Dict, List


def _compact_dimension(item: Dict[str, Any]) -> Dict[str, Any]:
    """保留人工复核所需的指标、系数、状态和证据来源。"""
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "side": item.get("side"),
        "score": item.get("score"),
        "coefficient": item.get("coefficient"),
        "status": item.get("status"),
        "evidence_refs": item.get("evidence_refs", []),
    }


def _question_for_dimension(item: Dict[str, Any], respondent: str) -> Dict[str, Any]:
    """按指标类型生成问题，避免把薪资、地点等信息一律问成STAR案例。"""
    indicator_id = str(item.get("id") or "")
    focus = str(item.get("name") or indicator_id or "待核验项")
    common = {"focus": focus, "indicator_id": indicator_id, "respondent": respondent}
    if any(token in indicator_id for token in ("compensation", "salary", "bonus")):
        return {**common,
            "question": "请确认可接受的薪资范围、最低底线、固定与浮动部分，以及是否可协商；金额请同时说明月薪/年薪和薪数。" if respondent == "candidate" else "请确认该岗位预算范围、固定与浮动构成、发薪月数及可协商空间。",
            "score_anchor": "完整：范围、底线、结构和可协商项均明确；部分：只有总额；待补：口径或周期不清。",
            "evidence_to_request": "统一口径后的薪资范围与结构说明", "follow_up_if": "金额周期、币种或固定/浮动口径不一致时继续追问。"}
    if any(token in indicator_id for token in ("location", "commute")):
        return {**common,
            "question": "请列出可接受的办公地点、单程通勤上限，以及是否接受搬迁或阶段性出差。" if respondent == "candidate" else "请确认实际办公地点、通勤或驻场要求，以及是否提供搬迁支持。",
            "score_anchor": "完整：地点、时长与搬迁边界明确；部分：仅给出城市；待补：未说明。",
            "evidence_to_request": "地点、通勤时长和搬迁边界", "follow_up_if": "岗位地点与个人可接受范围不重合时确认替代方案。"}
    if "work_mode" in indicator_id or "schedule_flexibility" in indicator_id:
        return {**common,
            "question": "请确认可接受远程、混合或现场中的哪些方式，以及每周到岗天数和弹性边界。" if respondent == "candidate" else "请确认岗位采用远程、混合还是现场办公，并说明固定到岗和弹性安排。",
            "score_anchor": "完整：模式、频率和例外规则明确；部分：只有模式；待补：未说明。",
            "evidence_to_request": "工作方式与到岗规则", "follow_up_if": "双方模式不同或存在例外规则时继续确认。"}
    if any(token in indicator_id for token in ("culture", "manager_style", "values", "psychological_safety", "feedback")):
        return {**common,
            "question": "你偏好的协作或管理方式是什么？请用一次真实合作经历说明这种方式如何影响结果。" if respondent == "candidate" else "团队实际采用怎样的协作、反馈和管理方式？请给出近期真实例子。",
            "score_anchor": "优：偏好/做法清楚且有事实案例；中：描述清楚但无案例；待补：仅有抽象标签。",
            "evidence_to_request": "一次真实协作案例与具体行为", "follow_up_if": "回答只出现文化口号或性格标签时追问实际事件。"}
    if any(token in indicator_id for token in ("certification", "education", "language")):
        return {**common,
            "question": "请确认可核验材料、证书或成绩编号、取得日期和有效期；如尚未取得，请明确当前状态。",
            "score_anchor": "完整：名称、编号/材料、日期和有效状态齐全；部分：可描述但缺材料；待补：无法确认。",
            "evidence_to_request": "证书、成绩或学历材料的核验信息", "follow_up_if": "名称相近、已过期或材料主体不一致时复核。"}
    if any(token in indicator_id for token in ("availability", "start_date")):
        return {**common,
            "question": "最早可到岗日期是什么？当前通知期多长，是否存在已知的交接或时间约束？" if respondent == "candidate" else "岗位期望到岗日期和可接受的最晚日期分别是什么？",
            "score_anchor": "完整：具体日期、通知期与约束清楚；部分：只有大致月份；待补：未说明。",
            "evidence_to_request": "日期与通知期说明", "follow_up_if": "时间区间不重合时确认是否可调整。"}
    if indicator_id in {"total_experience", "skill_experience_years", "industry_experience", "leadership_experience"}:
        return {**common,
            "question": "请按开始和结束年月列出与目标岗位相关的经历，并分别说明全职、实习、兼职或并行项目；请标出重叠时间和可核验材料。" if respondent == "candidate" else "请确认岗位认可哪些经验类型、如何计算重叠时间，以及最低有效经验年限。",
            "score_anchor": "完整：起止年月、经历类型、相关职责、重叠时间和核验材料清楚；部分：只有总年限；待补：时间线无法核对。",
            "evidence_to_request": "连续经历时间线、劳动或项目证明、本人职责说明",
            "follow_up_if": "总年限与时间线不一致、经历重叠或相关性不清时逐段复核。"}
    if any(token in indicator_id for token in ("skill", "toolchain", "domain")):
        return {**common,
            "question": f"请说明与“{focus}”可迁移的真实经历；若当前有差距，请给出学习计划、练习产物和预计验证时间。",
            "score_anchor": "优：可迁移经历具体且计划可验收；中：有相关经历但迁移路径模糊；待补：只有学习意愿。",
            "evidence_to_request": "相关项目、练习产物与学习里程碑", "follow_up_if": "只说‘了解/学过’时追问本人行动、结果和演示材料。"}
    return {**common,
        "question": f"请用STAR方式说明与“{focus}”相关的一次真实经历：情境、任务、本人行动和结果分别是什么？",
        "score_anchor": "优：情境、本人行动和结果清晰且可核验；中：案例基本完整但贡献或结果模糊；待补：只有自我评价。",
        "evidence_to_request": "过程材料、产出、指标口径或可验证的第三方信息", "follow_up_if": "本人贡献、结果口径或事实边界不清时继续追问。"}


def build_recommendations(result: Dict[str, Any]) -> Dict[str, Any]:
    """生成不夸大结论的双向行动清单。"""
    matrix = result.get("evidence_matrix", [])
    missing = [row for row in matrix if row.get("type") == "required_skill" and row.get("status") == "missing"]
    partial = [row for row in matrix if row.get("type") == "required_skill" and row.get("status") == "partial"]
    unverified = [row for row in matrix if row.get("type") == "responsibility" and row.get("status") == "unverified"]
    explicit_gaps = [str(row.get("requirement")) for row in missing if row.get("requirement")]
    matrix_verification = [str(row.get("requirement")) for row in partial + unverified if row.get("requirement")]

    dimensions = result.get("recruiter_dimensions", []) + result.get("candidate_dimensions", [])
    unknown = sorted(
        [item for item in dimensions if item.get("effective_score") is None and item.get("status") != "not_applicable"],
        key=lambda item: (-(item.get("coefficient") or 0), str(item.get("id"))),
    )
    low_known = sorted(
        [item for item in dimensions if item.get("score") is not None and float(item.get("score")) < 60],
        key=lambda item: (float(item.get("score")), -(item.get("coefficient") or 0)),
    )
    evidence_needed = [_compact_dimension(item) for item in unknown[:12]]
    verified_gaps = [_compact_dimension(item) for item in low_known[:10]]

    plan_skills = explicit_gaps[:2]
    plan = {
        "days_0_30": [f"学习并完成“{skill}”的最小可演示练习" for skill in plan_skills]
        or ["整理一项真实经历，写清背景、个人行动、结果指标和可核验材料"],
        "days_31_60": [f"围绕“{skill}”完成贴近岗位职责的实战项目" for skill in plan_skills]
        or ["用目标岗位的真实场景完成一次端到端案例并接受同伴评审"],
        "days_61_90": ["用可量化结果更新材料，并进行一次基于统一评分表的模拟面试"],
        "success_evidence": ["可演示产物", "量化结果或前后对比", "本人贡献说明", "第三方或过程材料"],
    }

    interview: List[Dict[str, Any]] = []
    seen = set()
    for requirement in explicit_gaps + matrix_verification:
        if requirement in seen:
            continue
        seen.add(requirement)
        interview.append({
            "focus": requirement,
            "indicator_id": "required_skill_gap",
            "respondent": "candidate",
            "question": f"请描述你在真实项目中使用或迁移到“{requirement}”的经历：当时目标是什么、你做了什么、结果如何？",
            "score_anchor": "优：情境和本人行动清晰，有量化结果及可核验材料；中：有案例但贡献或结果模糊；待补：只有概念描述。",
            "evidence_to_request": "项目材料、指标口径、产出链接或可说明过程的第三方信息",
            "follow_up_if": "只描述团队成果、学习经历或概念时，追问本人贡献和可演示产物。",
        })
    recruiter_unknown = [item for item in unknown if item.get("side") == "recruiter"]
    recruiter_low = [item for item in low_known if item.get("side") == "recruiter"]
    for item in (recruiter_unknown + recruiter_low)[:12]:
        focus = str(item.get("name") or item.get("id"))
        if focus in seen:
            continue
        seen.add(focus)
        question = _question_for_dimension(item, "candidate")
        if item.get("evidence_refs"):
            question["evidence_to_request"] = item["evidence_refs"]
        interview.append(question)

    job_confirmation = []
    for item in [value for value in (unknown + low_known) if value.get("side") == "candidate"][:14]:
        job_confirmation.append(_question_for_dimension(item, "employer"))
    covered_confirmation_ids = {str(item.get("indicator_id") or "") for item in job_confirmation}
    baseline_confirmations = [
        {"id": "compensation_alignment", "name": "薪酬范围与构成"},
        {"id": "location_preference_alignment", "name": "实际办公地点与通勤要求"},
        {"id": "work_mode_preference_alignment", "name": "远程、混合或现场安排"},
        {"id": "manager_style_alignment", "name": "团队管理与反馈方式"},
        {"id": "start_date_alignment", "name": "岗位到岗时间"},
    ]
    for item in baseline_confirmations:
        if item["id"] not in covered_confirmation_ids:
            job_confirmation.append(_question_for_dimension(item, "employer"))
    baseline_ids = {item["id"] for item in baseline_confirmations}
    baseline_questions = [item for item in job_confirmation if item.get("indicator_id") in baseline_ids]
    other_questions = [item for item in job_confirmation if item.get("indicator_id") not in baseline_ids]
    job_confirmation = (baseline_questions + other_questions)[:14]

    resume_actions = [f"若确有经历，为“{name}”补充项目背景、本人行动和量化结果" for name in matrix_verification[:5]]
    if explicit_gaps:
        resume_actions.append("不要把尚未掌握的技能写成已掌握；学习中或在做项目应明确标注状态")
    if not resume_actions:
        resume_actions.append("把已有经历改写为背景—行动—结果，并注明本人贡献与可核验指标")

    return {
        "explicit_requirement_gaps": explicit_gaps,
        "verified_gaps": verified_gaps,
        "needs_verification": matrix_verification,
        "evidence_needed": evidence_needed,
        "development_plan": plan,
        "interview_questions": interview[:14],
        "job_confirmation_questions": job_confirmation,
        "resume_actions": resume_actions,
        "recruiter_actions": [
            "先补高系数未知项，再比较候选人；资料缺失不等于能力不足",
            "所有候选人使用同一核心问题和评分锚点，必要追问单独记录",
            "将系统结果作为人工复核线索，不作为自动录用或淘汰决定",
        ],
        "candidate_actions": [
            "确认薪酬、地点、工作方式、成长机会等岗位侧未知条件",
            "只陈述真实经历，无法核验的内容标注为个人说明",
        ],
    }
