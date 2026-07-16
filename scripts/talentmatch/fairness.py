"""本模块只审计用户填写的文本和值，识别公平性条件和嵌入式指令风险。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import re

from .governance_constants import (
    INJECTION_PATTERNS,
    PROTECTED_FIELD_CATEGORIES,
    PROTECTED_PATTERNS,
    TECHNICAL_KEYS,
    protected_paths,
    sanitize_record_for_scoring,
)

# 保留旧名称，外部调用不需要随内部重构修改。
PROTECTED_FIELD_KEYS = PROTECTED_FIELD_CATEGORIES


def audit_text(text: str) -> Dict[str, Any]:
    """审计一段用户文本，不检查承载它的内部字段名。"""
    source = str(text or "")
    flags: List[Dict[str, Any]] = []
    for category, pattern in PROTECTED_PATTERNS.items():
        matches = list(re.finditer(pattern, source, flags=re.IGNORECASE))
        if matches:
            flags.append({"category": category, "count": len(matches), "action": "exclude_from_scoring_and_review"})
    injection_count = len(list(INJECTION_PATTERNS.finditer(source)))
    return {
        "protected_trait_flags": flags,
        "prompt_injection_flags": injection_count,
        "safe_for_scoring": not flags,
        "note": "仅标记风险类别，不复述敏感值，也不执行输入中的指令。",
    }


def _iter_user_text(value: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[str, str]]:
    """递归枚举用户文本值，同时跳过评分引擎自己的技术字段。"""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in TECHNICAL_KEYS:
                continue
            yield from _iter_user_text(child, (*path, key_text))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _iter_user_text(child, (*path, str(index)))
    elif isinstance(value, str) and value.strip():
        yield ".".join(path), value


def _iter_field_keys(value: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[str, str]]:
    """枚举结构化字段名，用于发现直接传入的受保护属性字段。"""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            yield ".".join((*path, key_text)), key_text
            yield from _iter_field_keys(child, (*path, key_text))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _iter_field_keys(child, (*path, str(index)))


def audit_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """审计结构化候选人或岗位记录，只扫描用户值并单独识别受保护字段名。"""
    all_flags: List[Dict[str, Any]] = []
    injection_details: List[Dict[str, Any]] = []

    for field_path, key in _iter_field_keys(record):
        category = PROTECTED_FIELD_KEYS.get(key.casefold())
        if category:
            all_flags.append({
                "category": category,
                "count": 1,
                "action": "exclude_from_scoring_and_review",
                "field_path": field_path,
                "source": "structured_field",
            })

    for field_path, text in _iter_user_text(record):
        audit = audit_text(text)
        for flag in audit["protected_trait_flags"]:
            all_flags.append({**flag, "field_path": field_path, "source": "user_value"})
        if audit["prompt_injection_flags"]:
            injection_details.append({"field_path": field_path, "count": audit["prompt_injection_flags"]})

    unique: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for flag in all_flags:
        key = (str(flag.get("category")), str(flag.get("field_path")))
        unique[key] = flag
    flags = list(unique.values())
    return {
        "protected_trait_flags": flags,
        "prompt_injection_flags": sum(item["count"] for item in injection_details),
        "prompt_injection_details": injection_details,
        "safe_for_scoring": not flags,
        "excluded_structured_paths": sorted(set(protected_paths(record))),
        "note": "仅审计用户文本值和明确的受保护字段；评分技术字段不会触发公平性风险。",
    }


def sanitize_for_scoring(record: Dict[str, Any]) -> Dict[str, Any]:
    """返回不含受保护字段、敏感短语和嵌入式指令的评分副本。"""
    cleaned = sanitize_record_for_scoring(record)
    return cleaned if isinstance(cleaned, dict) else {}
