"""本模块校验外部语义抽取结果，使任何模型只负责抽取，确定性引擎仍负责评分。"""

from __future__ import annotations

from typing import Any, Dict, Iterable

from .governance_constants import PROTECTED_FIELD_KEYS
from .parser import parse_candidate, parse_job
from .text import normalize_text


def _walk_keys(value: Any, path: str = "") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            field_path = f"{path}.{key}" if path else str(key)
            yield field_path
            yield from _walk_keys(child, field_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def validate_semantic_extraction(payload: Dict[str, Any]) -> Dict[str, Any]:
    """验证字段、证据原文和受保护属性，返回可交给评分引擎的规范数据。"""
    if not isinstance(payload, dict):
        raise ValueError("语义抽取结果必须是JSON对象")
    candidate = payload.get("candidate")
    job = payload.get("job")
    if not isinstance(candidate, dict) or not isinstance(job, dict):
        raise ValueError("语义抽取结果必须同时包含 candidate 和 job 对象")

    protected_paths = []
    for root_name, record in (("candidate", candidate), ("job", job)):
        for field_path in _walk_keys(record):
            leaf = field_path.rsplit(".", 1)[-1].split("[", 1)[0].casefold()
            if leaf in PROTECTED_FIELD_KEYS:
                protected_paths.append(f"{root_name}.{field_path}")
    if protected_paths:
        raise ValueError("抽取结果包含不得进入评分结构的受保护属性：" + "、".join(protected_paths))

    claims = payload.get("extraction", {}).get("claims", []) if isinstance(payload.get("extraction"), dict) else []
    source_text = normalize_text(str(candidate.get("source_text", "")) + "\n" + str(job.get("source_text", ""))).casefold()
    ungrounded = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or not str(claim.get("field_path", "")).strip():
            raise ValueError(f"extraction.claims[{index}] 缺少 field_path")
        quote = normalize_text(claim.get("source_quote", ""))
        if quote and quote.casefold() not in source_text:
            ungrounded.append(index)
    if ungrounded:
        raise ValueError("以下抽取结论的 source_quote 无法在原文中定位：" + "、".join(map(str, ungrounded)))

    return {
        "candidate": parse_candidate(candidate),
        "job": parse_job(job),
        "validation": {
            "valid": True,
            "grounded_claim_count": len(claims),
            "protected_attributes_used": False,
            "scoring_owner": "deterministic_engine",
            "network_required": False,
        },
    }


def semantic_extraction_contract() -> Dict[str, Any]:
    """返回跨平台模型适配器应遵守的最小契约。"""
    return {
        "candidate": "候选人结构化对象，保留 source_text",
        "job": "岗位结构化对象，可包含 requirement_groups",
        "extraction": {"claims": [{"field_path": "字段路径", "value": "抽取值", "source_quote": "原文片段"}]},
        "rules": [
            "模型只抽取和归一，不直接给匹配分",
            "每个新增事实尽量附原文片段",
            "且/或要求写入 requirement_groups",
            "受保护属性不得写入评分结构",
            "输出先通过本地校验，再交给确定性评分引擎",
        ],
    }
