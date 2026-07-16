"""本模块集中定义受保护属性、技术字段和评分前文本净化规则。"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Tuple


# 字段名与风险类别统一放在这里，公平性审计和语义适配器共用同一份定义。
PROTECTED_FIELD_CATEGORIES = {
    "age": "age", "birth_date": "age", "date_of_birth": "age", "birthdate": "age", "birthday": "age",
    "年龄": "age", "出生日期": "age", "出生年月": "age",
    "gender": "gender", "sex": "gender", "性别": "gender",
    "marital_status": "marital_family", "family_status": "marital_family", "pregnancy": "marital_family",
    "婚姻": "marital_family", "婚育": "marital_family",
    "height": "appearance", "body_weight": "appearance", "photo": "appearance",
    "身高": "appearance", "体重": "appearance", "照片": "appearance",
    "disability": "health_disability", "health_status": "health_disability", "medical_condition": "health_disability",
    "健康状况": "health_disability", "残障": "health_disability",
    "ethnicity": "ethnicity_religion", "race": "ethnicity_religion", "religion": "ethnicity_religion",
    "民族": "ethnicity_religion", "宗教": "ethnicity_religion",
    "political_affiliation": "politics", "政治面貌": "politics",
    "household_registration": "origin_proxy", "native_place": "origin_proxy",
    "户籍": "origin_proxy", "籍贯": "origin_proxy",
}
PROTECTED_FIELD_KEYS = frozenset(PROTECTED_FIELD_CATEGORIES)

# 这些键属于评分结构，不是用户对外貌、体重或身份条件的表达。
TECHNICAL_KEYS = frozenset({
    "weight", "coefficient", "normalized_weight_percent", "contribution", "score",
    "effective_score", "row", "enabled", "hard", "parser", "certainty", "warnings",
})

PROTECTED_PATTERNS = {
    "age": r"年龄|\d{1,3}\s*岁(?:以下|以上|以内|左右)?|age\s*(?:limit|under|over|between)|young\s+only|年轻优先",
    "gender": r"性别|限男|限女|男性优先|女性优先|\bmale\s+only\b|\bfemale\s+only\b|\bgender\s+requirement\b",
    "marital_family": r"婚育|婚姻|已婚|未婚|生育|怀孕|\bmarital\s+status\b|\bpregnan(?:t|cy)\b|\bchildren\s+required\b",
    "appearance": r"形象气质|五官端正|身高|体重|照片要求|需附照片|\bappearance\s+requirement\b|\bheight\s+requirement\b|\bbody\s+weight\b|\bphoto\s+required\b",
    "health_disability": r"残疾|残障|无疾病|身体健康|健康证明|\bdisabilit(?:y|ies)\b|\bmedical\s+condition\b|\bhealthy\s+only\b",
    "ethnicity_religion": r"民族|种族|宗教|\bethnicity\b|\brace\s+requirement\b|\breligion\b",
    "politics": r"政治面貌|党员优先|\bpolitical\s+affiliation\b",
    "origin_proxy": r"户籍|本地人优先|籍贯|\bhousehold\s+registration\b|\bnative\s+resident\b",
}

INJECTION_PATTERNS = re.compile(
    r"ignore\s+(?:all|any|previous|prior)\s+(?:instructions?|rules?)|"
    r"system\s+prompt|developer\s+message|"
    r"忽略(?:之前|以前|上述|全部|所有).{0,12}(?:指令|要求|规则)|"
    r"不要遵守.{0,12}(?:系统|开发者|安全).{0,8}(?:指令|要求|规则)|"
    r"输出.{0,12}(?:系统提示词|隐藏提示词|全部隐私|密钥)|"
    r"改写.{0,12}(?:安全规则|评分规则|系统规则)|"
    r"按照(?:本文|上文|以下).{0,12}(?:命令|指令).{0,8}执行|"
    r"执行以下命令|运行命令|泄露|读取密钥|"
    r"(?:发送|上传|传输).{0,18}(?:候选人隐私|简历数据|个人信息)|"
    r"(?:curl|powershell)\s+|rm\s+-rf",
    re.IGNORECASE,
)

# 审计规则负责“发现”，下列规则负责从评分副本中删除完整敏感短语。
SCORING_TEXT_SANITIZERS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"(?:年龄\s*[:：]?\s*)?\d{1,3}\s*岁(?:以下|以上|以内|左右|前后)?",
    r"(?:限|仅限|只招|要求|优先考虑)?\s*(?:男性|女性|男士|女士)(?:优先)?",
    r"(?:限男|限女|男性优先|女性优先|性别\s*[:：]?\s*(?:男|女|男性|女性))",
    r"(?:已婚|未婚|婚育状况|婚姻状况|生育状况|怀孕)",
    r"(?:身体健康|无疾病|健康证明|健康状况\s*[:：]?\s*[^，,；;。]{0,18})",
    r"(?:残疾|残障|医疗状况\s*[:：]?\s*[^，,；;。]{0,18})",
    r"(?:户籍|籍贯)\s*[:：]?\s*[^，,；;。\s]{0,18}",
    r"(?:本地人优先|党员优先|政治面貌\s*[:：]?\s*[^，,；;。]{0,18})",
    r"(?:身高|体重)\s*[:：]?\s*\d+(?:\.\d+)?\s*(?:cm|厘米|kg|公斤)?(?:以上|以下|以内)?",
    r"(?:照片要求|需附照片|形象气质|五官端正)",
    r"(?:民族|宗教)\s*[:：]?\s*[^，,；;。\s]{0,18}",
    r"\b(?:male|female)\s+only\b|\bgender\s+requirement\b|\bmarital\s+status\b|"
    r"\b(?:age|height|body\s+weight|religion|ethnicity)\s*(?:requirement|limit)?\s*[:：]?\s*[^,;。]{0,24}",
))


def protected_category_for_key(key: Any) -> str | None:
    """返回结构化字段对应的受保护属性类别。"""
    return PROTECTED_FIELD_CATEGORIES.get(str(key).casefold())


def sanitize_text_for_scoring(text: Any) -> str:
    """删除敏感短语和嵌入式指令，并消除删除后残留的标点差异。"""
    cleaned = str(text or "")
    for pattern in SCORING_TEXT_SANITIZERS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = INJECTION_PATTERNS.sub(" ", cleaned)
    cleaned = re.sub(r"[，,；;：:|]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .。；;，,")


def sanitize_record_for_scoring(value: Any, path: Tuple[str, ...] = ()) -> Any:
    """递归生成评分专用副本；受保护字段整字段排除，原始对象保持不变。"""
    if isinstance(value, dict):
        output: Dict[str, Any] = {}
        for key, child in value.items():
            if protected_category_for_key(key):
                continue
            cleaned = sanitize_record_for_scoring(child, (*path, str(key)))
            output[key] = cleaned
        return output
    if isinstance(value, (list, tuple)):
        output = [sanitize_record_for_scoring(child, (*path, str(index))) for index, child in enumerate(value)]
        return [child for child in output if child not in (None, "")]
    if isinstance(value, str):
        return sanitize_text_for_scoring(value)
    return value


def protected_paths(record: Any, path: Tuple[str, ...] = ()) -> Iterable[str]:
    """枚举会被评分副本排除的结构化字段路径。"""
    if isinstance(record, dict):
        for key, child in record.items():
            next_path = (*path, str(key))
            if protected_category_for_key(key):
                yield ".".join(next_path)
            else:
                yield from protected_paths(child, next_path)
    elif isinstance(record, (list, tuple)):
        for index, child in enumerate(record):
            yield from protected_paths(child, (*path, str(index)))
