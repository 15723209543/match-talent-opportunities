"""本模块把候选人和岗位原始文本保守解析为可评分的结构化数据。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .model import as_list, normalize_candidate, normalize_job
from .ontology import canonicalize, find_skills
from .text import compact_snippet, extract_years, normalize_text


PREFERRED_MARKERS = re.compile(r"优先|加分|preferred|nice[ -]to[ -]have|plus", re.I)
HARD_MARKERS = re.compile(r"必须|硬性|mandatory|required|must\b|不得低于", re.I)
GLOBAL_HARD_SCOPE = re.compile(r"(?:以下|下列|上述|全部|所有).{0,12}(?:均|都|全部)?(?:为|是)?(?:必须|硬性)", re.I)
GLOBAL_PREFERRED_SCOPE = re.compile(r"(?:以下|下列|上述|这些|全部|所有).{0,12}(?:均|都|全部)?(?:为|是)?(?:优先|加分)", re.I)
HARD_SCOPE_HEADING = re.compile(r"^(?:必须|硬性)(?:条件|要求|技能|资格|项|清单)?\s*[:：]?\s*$", re.I)
PREFERRED_SCOPE_HEADING = re.compile(r"^(?:优先|加分)(?:条件|要求|技能|资格|项|清单)?\s*[:：]?\s*$", re.I)
NORMAL_SECTION_START = re.compile(
    r"^(?:岗位职责|工作职责|职位职责|工作内容|职位描述|岗位描述|任职要求|岗位要求|职位要求|任职资格|基本要求|"
    r"薪资(?:待遇|福利)?|薪酬(?:待遇|福利)?|福利待遇|工作地点|办公地点|办公方式|职位信息|关于我们|我们提供)\s*[:：]?",
    re.I,
)
SALARY_MARKERS = re.compile(r"薪资|薪酬|待遇|月薪|年薪|底薪|期望薪资|salary|compensation|pay\b|package|面议", re.I)
SALARY_UNIT = r"k|w|千|万|元"
OR_MARKERS = re.compile(r"(?:\bor\b|或(?:者)?|任选|任一|其中.{0,8}至少|中.{0,8}至少)", re.I)
GROUP_WIDE_OR_MARKERS = re.compile(r"(?:中|其中).{0,8}至少|任选|任一|任意.{0,4}(?:一|\d)", re.I)


def _canonicalize_items(items: List[Any]) -> List[Dict[str, Any]]:
    output = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            data = {"name": item}
        elif isinstance(item, dict):
            data = dict(item)
        else:
            data = {"name": str(item)}
        original = str(data.get("name", "")).strip()
        canonical = canonicalize(original)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        data["name"] = canonical
        if original.casefold() != canonical.casefold():
            data.setdefault("original_name", original)
        output.append(data)
    return output


def _field_from_line(lines: List[str], markers: str) -> str:
    pattern = re.compile(markers, re.I)
    for line in lines:
        if pattern.search(line):
            parts = re.split(r"[:：]", line, maxsplit=1)
            return parts[-1].strip() if len(parts) > 1 else line.strip()
    return ""


def _education_level(text: str) -> str | None:
    levels = [
        (r"博士|ph\.?d|doctorate", "doctorate"),
        (r"硕士|研究生|master|mba", "master"),
        (r"本科|学士|bachelor", "bachelor"),
        (r"大专|专科|associate", "associate"),
        (r"高中|high school", "high-school"),
    ]
    for pattern, level in levels:
        if re.search(pattern, text, re.I):
            return level
    return None


def _salary(text: str) -> Dict[str, Any]:
    """解析常见中文薪资写法，并主动排除日期、年龄和经验区间。"""
    source = normalize_text(text).casefold()
    if not source:
        return {}

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    candidates = [line for line in lines if SALARY_MARKERS.search(line)]
    candidates.extend(line for line in lines if line not in candidates)
    if not candidates:
        candidates = [source]

    def multiplier(unit: str) -> float:
        return 1000.0 if unit in {"k", "千"} else 10000.0 if unit in {"w", "万"} else 1.0

    def decorate(result: Dict[str, Any], segment: str) -> Dict[str, Any]:
        annual = bool(re.search(r"年薪|/\s*年|每年|万元?\s*/\s*年", segment))
        result.update({"currency": "CNY", "period": "year" if annual else "month"})
        months_range = re.search(r"[·x×*]\s*(1[0-9]|[1-9])\s*[-~～—–至到]\s*(1[0-9]|[1-9])\s*薪", segment, re.I)
        if months_range:
            low, high = int(months_range.group(1)), int(months_range.group(2))
            result["salary_months_min"] = min(low, high)
            result["salary_months_max"] = max(low, high)
        months = re.search(r"[·x×*]\s*(1[0-9]|[1-9])\s*薪", segment, re.I)
        if months and not months_range:
            result["salary_months"] = int(months.group(1))
        if re.search(r"绩效|奖金|提成|bonus|commission", segment, re.I):
            result["variable_component"] = True
        if "面议" in segment or re.search(r"negotiable", segment, re.I):
            result["negotiable"] = True
        return result

    range_pattern = re.compile(
        rf"(?<!\d)(\d+(?:\.\d+)?)\s*({SALARY_UNIT})?\s*"
        rf"[-~～—–至到]\s*(\d+(?:\.\d+)?)\s*({SALARY_UNIT})?"
    )
    single_pattern = re.compile(rf"(?<!\d)(\d+(?:\.\d+)?)\s*({SALARY_UNIT})(?!\s*[-~～—–至到]\s*\d)")
    lower_prefix_pattern = re.compile(rf"(?:不低于|不少于|至少|最低)\s*(\d+(?:\.\d+)?)\s*({SALARY_UNIT})")
    lower_suffix_pattern = re.compile(rf"(?<!\d)(\d+(?:\.\d+)?)\s*({SALARY_UNIT})\s*(?:以上|起(?:步)?)")
    upper_prefix_pattern = re.compile(rf"(?:不超过|不高于|至多|最高)\s*(\d+(?:\.\d+)?)\s*({SALARY_UNIT})")
    upper_suffix_pattern = re.compile(rf"(?<!\d)(\d+(?:\.\d+)?)\s*({SALARY_UNIT})\s*(?:以内|以下|封顶)")

    for segment in candidates:
        has_context = bool(SALARY_MARKERS.search(segment))
        match = range_pattern.search(segment)
        if match:
            low, high = float(match.group(1)), float(match.group(3))
            first_unit, second_unit = match.group(2) or "", match.group(4) or ""
            unit = second_unit or first_unit
            has_explicit_salary_unit = bool(unit or re.search(r"/\s*[月年]|每[月年]|\d+\s*薪", segment))
            looks_like_calendar = low.is_integer() and high.is_integer() and 1900 <= low <= 2100 and 1900 <= high <= 2100
            looks_like_age_or_experience = bool(re.search(r"岁|年龄|年(?:以上)?经验|经验.{0,4}年", segment))
            if (not has_context and not has_explicit_salary_unit) or looks_like_calendar or looks_like_age_or_experience:
                continue
            if not unit and max(low, high) < 100:
                continue
            low_value = low * multiplier(first_unit or unit)
            high_value = high * multiplier(second_unit or unit)
            if high_value < low_value:
                low_value, high_value = high_value, low_value
            return decorate({"min": low_value, "max": high_value}, segment)

        lower = lower_prefix_pattern.search(segment) or lower_suffix_pattern.search(segment)
        if lower:
            amount = float(lower.group(1)) * multiplier(lower.group(2))
            return decorate({"min": amount, "max": None}, segment)

        upper = upper_prefix_pattern.search(segment) or upper_suffix_pattern.search(segment)
        if upper:
            amount = float(upper.group(1)) * multiplier(upper.group(2))
            return decorate({"min": None, "max": amount}, segment)

        single = single_pattern.search(segment)
        if single and has_context:
            amount = float(single.group(1)) * multiplier(single.group(2))
            return decorate({"min": amount, "max": amount}, segment)

        if has_context and ("面议" in segment or re.search(r"negotiable", segment, re.I)):
            return decorate({"negotiable": True}, segment)
    return {}


def _minimum_match_count(text: str, item_count: int) -> int:
    """从“至少两项”等表达中提取最低命中数，结果不会超过组内技能数。"""
    match = re.search(r"至少\s*([一二两三四五六七八九十\d]+)\s*(?:种|项|个|门)?", text)
    if not match:
        return 1
    count_text = match.group(1)
    chinese = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    value = int(count_text) if count_text.isdigit() else chinese.get(count_text, 1)
    return max(1, min(item_count, value))


def _semantic_skill_clauses(clause: str) -> List[str]:
    """把顿号列表中的独立必选项与末尾OR组选项分开，组级“至少N项”保持整体。"""
    if "、" not in clause or not OR_MARKERS.search(clause) or GROUP_WIDE_OR_MARKERS.search(clause):
        return [clause]
    parts = [part.strip() for part in clause.split("、") if part.strip()]
    return parts or [clause]


def _mode_is_positive(text: str, token_pattern: str) -> bool:
    """识别办公方式的肯定表达，并排除“不接受/不支持/仅现场”等否定语境。"""
    source = normalize_text(text)
    before_negative = re.compile(r"(?:不接受|不支持|不提供|不考虑|暂不考虑|暂不支持|不可|不能|拒绝|禁止|不希望|非)\s*$", re.I)
    after_negative = re.compile(r"^\s*(?:办公)?\s*(?:均|都)?\s*(?:暂不支持|暂不考虑|不支持|不接受|不可|不能|不提供|不考虑|禁止|not\s+supported)", re.I)
    for match in re.finditer(token_pattern, source, re.I):
        before = source[max(0, match.start() - 12):match.start()]
        after = source[match.end():match.end() + 12]
        if before_negative.search(before) or after_negative.search(after):
            continue
        return True
    return False


def _extract_work_modes(text: str) -> List[str]:
    """从候选人或岗位自然语言中提取未被否定的远程、混合和现场方式。"""
    modes = []
    only_onsite = bool(re.search(r"(?:仅|只)(?:限|支持|接受|考虑|能)?\s*(?:现场|坐班|onsite|on-site)", text, re.I))
    if not only_onsite and _mode_is_positive(text, r"远程|remote"):
        modes.append("remote")
    if not only_onsite and _mode_is_positive(text, r"混合|hybrid"):
        modes.append("hybrid")
    if _mode_is_positive(text, r"现场|坐班|onsite|on-site"):
        modes.append("onsite")
    return modes


def _context_is_hard(lines: List[str], context_pattern: str) -> bool:
    """只让硬条件标记作用于包含目标条件的当前子句，显式全局声明除外。"""
    marker = re.compile(context_pattern, re.I)
    for clause, scope in _scoped_clauses(lines):
        if marker.search(clause) and (scope == "hard" or HARD_MARKERS.search(clause)):
            return True
    return False


def _line_scope_directive(line: str) -> str | None:
    """识别列表标题的作用域，并在进入新章节时恢复普通要求。"""
    cleaned = normalize_text(line).strip(" -•\t")
    if GLOBAL_HARD_SCOPE.search(cleaned) or HARD_SCOPE_HEADING.fullmatch(cleaned):
        return "hard"
    if GLOBAL_PREFERRED_SCOPE.search(cleaned) or PREFERRED_SCOPE_HEADING.fullmatch(cleaned):
        return "preferred"
    if NORMAL_SECTION_START.search(cleaned):
        return "normal"
    if re.fullmatch(r"[^，,;；。]{1,24}[:：]", cleaned):
        return "normal"
    return None


def _scoped_clauses(lines: List[str]):
    """逐行生成带段落作用域的子句，供技能和经验硬条件共用。"""
    current_scope = "normal"
    for line in lines:
        directive = _line_scope_directive(line)
        if directive is not None:
            current_scope = directive
        for clause in [part.strip() for part in re.split(r"[，,;；。]", line) if part.strip()]:
            yield clause, current_scope


def _skill_requirements(text: str, lines: List[str]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """把岗位文本中的技能拆成且/或逻辑组，同时生成兼容旧接口的扁平清单。"""
    required: List[Dict[str, Any]] = []
    preferred: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    seen = set()
    group_index = 0
    for clause, scope in _scoped_clauses(lines):
        clause_hard = bool(scope == "hard" or HARD_MARKERS.search(clause))
        clause_preferred = bool(not clause_hard and (scope == "preferred" or PREFERRED_MARKERS.search(clause)))
        for semantic_clause in _semantic_skill_clauses(clause):
            detected = find_skills(semantic_clause)
            if not detected:
                continue
            names = [item["name"] for item in detected]
            identity = (tuple(names), semantic_clause.casefold())
            if identity in seen:
                continue
            seen.add(identity)
            group_index += 1
            explicit_choice = bool(OR_MARKERS.search(semantic_clause))
            slash_pair = len(names) >= 2 and bool(re.search(r"[a-z0-9+#.-]+\s*/\s*[a-z0-9+#.-]+", semantic_clause, re.I))
            needs_confirmation = bool(slash_pair and not explicit_choice)
            operator = "any" if explicit_choice or needs_confirmation else "all"
            minimum = _minimum_match_count(clause, len(names)) if operator == "any" else len(names)
            group_id = f"text-group-{group_index}"
            items = []
            for name in names:
                record = {
                    "name": name,
                    "years": extract_years(clause),
                    "hard": clause_hard,
                    "weight": 1.0,
                    "source": compact_snippet(semantic_clause, name),
                    "group_id": group_id,
                    "group_operator": operator,
                    "group_minimum_match_count": minimum,
                    "needs_confirmation": needs_confirmation,
                }
                items.append(dict(record))
                (preferred if clause_preferred else required).append(record)
            groups.append({
                "id": group_id,
                "operator": operator,
                "minimum_match_count": minimum,
                "items": items,
                "hard": clause_hard,
                "preferred": clause_preferred,
                "needs_confirmation": needs_confirmation,
                "ambiguity_reason": "slash_without_explicit_choice" if needs_confirmation else "",
                "weight": 1.0,
                "source": semantic_clause,
            })
    return required, preferred, groups


def parse_candidate(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        data = dict(value)
        skills_present = "skills" in data
        data["skills"] = _canonicalize_items(as_list(data.get("skills")))
        confirmed = str(data.get("skills_confirmed_complete", "")).strip().casefold() in {"true", "1", "yes", "y", "是", "真"}
        if not skills_present:
            status, confidence = "omitted", 0.0
        elif data["skills"]:
            status, confidence = "provided", 1.0
        elif confirmed:
            status, confidence = "explicit_empty", 1.0
        else:
            status, confidence = "inferred", 0.25
        provenance = dict(data.get("data_provenance") or {}) if isinstance(data.get("data_provenance"), dict) else {}
        provenance["skills"] = {
            "status": status,
            "source": "candidate_input",
            "confidence": confidence,
        }
        data["data_provenance"] = provenance
        return normalize_candidate(data)
    text = normalize_text(value)
    if not text:
        return normalize_candidate({
            "data_provenance": {"skills": {"status": "extraction_failed", "source": "candidate_text", "confidence": 0.0}},
            "parser": {"mode": "text", "certainty": 0.0, "warnings": ["empty_input"]},
        })
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    detected = find_skills(text)
    skills = []
    for item in detected:
        skill = item["name"]
        snippet = compact_snippet(text, item["aliases"][0])
        skill_years = extract_years(snippet)
        skills.append({"name": skill, "years": skill_years, "evidence": snippet})
    target = _field_from_line(lines, r"求职意向|目标岗位|应聘职位|target role|objective")
    location = _field_from_line(lines, r"期望地点|工作地点|location|base")
    work_modes = _extract_work_modes(text)
    level = _education_level(text)
    warnings = ["raw_text_parser_requires_review"]
    if not detected:
        warnings.append("no_known_skills_detected")
    data = {
        "target_roles": [target] if target else [],
        "summary": compact_snippet(text, limit=240),
        "skills": skills,
        "experience_years": extract_years(text),
        "education": [{"level": level}] if level else [],
        "preferred_locations": [location] if location else [],
        "preferred_work_modes": work_modes,
        "salary_expectation": _salary(text),
        "data_provenance": {
            "skills": {
                "status": "provided" if skills else "extraction_failed",
                "source": "candidate_text_parser",
                "confidence": 0.68 if skills else 0.0,
            }
        },
        "source_text": text,
        "parser": {"mode": "text", "certainty": 0.68 if detected else 0.45, "warnings": warnings},
    }
    return normalize_candidate(data)


def parse_job(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        data = dict(value)
        data["required_skills"] = _canonicalize_items(as_list(data.get("required_skills")))
        data["preferred_skills"] = _canonicalize_items(as_list(data.get("preferred_skills")))
        return normalize_job(data)
    text = normalize_text(value)
    if not text:
        return normalize_job({"parser": {"mode": "text", "certainty": 0.0, "warnings": ["empty_input"]}})
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    title = _field_from_line(lines, r"职位名称|岗位名称|招聘职位|job title|position")
    if not title:
        title = lines[0][:80] if lines else ""
    required, preferred, requirement_groups = _skill_requirements(text, lines)
    responsibilities = []
    in_responsibilities = False
    for line in lines:
        if re.search(r"岗位职责|工作职责|responsibilit|what you.?ll do", line, re.I):
            in_responsibilities = True
            continue
        if re.search(r"任职要求|岗位要求|qualifications|requirements|任职资格", line, re.I):
            in_responsibilities = False
            continue
        if in_responsibilities and len(line) >= 4:
            responsibilities.append(line[:240])
    location = _field_from_line(lines, r"工作地点|办公地点|location|base") or None
    work_modes = _extract_work_modes(text)
    level = _education_level(text)
    experience_lines = [line for line in lines if re.search(r"经验|从事|experience|years?", line, re.I)]
    min_years = extract_years("\n".join(experience_lines))
    parser_warnings = ["raw_text_parser_requires_review"]
    if any(group.get("needs_confirmation") for group in requirement_groups):
        parser_warnings.append("ambiguous_slash_requirement_requires_confirmation")
    data = {
        "title": title,
        "summary": compact_snippet(text, limit=240),
        "responsibilities": responsibilities,
        "required_skills": required,
        "preferred_skills": preferred,
        "requirement_groups": requirement_groups,
        "min_experience_years": min_years,
        "experience_hard": bool(min_years is not None and _context_is_hard(lines, r"经验|从事|experience|years?")),
        "education": {"min_level": level, "hard": bool(level and _context_is_hard(lines, r"博士|硕士|研究生|本科|学士|大专|专科|高中|education|degree|bachelor|master"))} if level else {},
        "location": location,
        "work_modes": work_modes,
        "salary_range": _salary(text),
        "source_text": text,
        "parser": {
            "mode": "text",
            "certainty": 0.58 if any(group.get("needs_confirmation") for group in requirement_groups) else 0.7 if required else 0.48,
            "warnings": parser_warnings,
        },
    }
    return normalize_job(data)
