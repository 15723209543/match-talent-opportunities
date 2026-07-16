"""本模块加载技能本体并处理中英文别名、同义技能和可迁移技能关系。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .text import key_text, normalize_text


ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "references" / "skill-ontology.json"


@lru_cache(maxsize=1)
def load_ontology() -> Dict:
    with ONTOLOGY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1024)
def canonicalize(name: str) -> str:
    needle = key_text(name)
    if not needle:
        return ""
    for canonical, aliases in load_ontology().get("skills", {}).items():
        if needle == key_text(canonical) or any(needle == key_text(alias) for alias in aliases):
            return canonical
    return normalize_text(name).casefold().replace(" ", "-")


def _contains(text: str, alias: str) -> bool:
    lowered = text.casefold()
    alias_lower = normalize_text(alias).casefold()
    if not alias_lower:
        return False
    if alias_lower == "go":
        if re.search(r"(?:^|[、，,;/]|或(?:者)?\s*)Go(?=$|[、，,;/\s]|或|任选|任一|二选一|至少)", text):
            return True
        contextual_go = re.compile(
            r"(?:掌握|熟悉|精通|使用|采用|开发|研发|技能|技术栈|要求).{0,12}(?<![a-z0-9])go(?![a-z0-9])|"
            r"(?<![a-z0-9])go(?![a-z0-9])\s*(?:语言|开发|工程师|后端|技术栈)",
            re.I,
        )
        return bool(contextual_go.search(text))
    if re.search(r"[a-z0-9]", alias_lower) and not re.search(r"[\u3400-\u9fff]", alias_lower):
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(alias_lower) + r"(?![a-z0-9])", lowered))
    return alias_lower in lowered


def find_skills(text: str) -> List[Dict]:
    source = normalize_text(text)
    found = []
    for canonical, aliases in load_ontology().get("skills", {}).items():
        hits = [alias for alias in aliases if _contains(source, alias)]
        if hits:
            found.append({"name": canonical, "aliases": sorted(set(hits), key=len, reverse=True)[:3]})
    return sorted(found, key=lambda item: item["name"])


def relation(required: str, candidate_skills: Iterable[str]) -> Tuple[str, float, str]:
    required_c = canonicalize(required)
    candidates = {canonicalize(x): x for x in candidate_skills if canonicalize(x)}
    if required_c in candidates:
        return "exact", 1.0, required_c
    related = set(load_ontology().get("related", {}).get(required_c, []))
    for candidate_c in candidates:
        if candidate_c in related or required_c in set(load_ontology().get("related", {}).get(candidate_c, [])):
            return "partial", 0.35, candidate_c
    return "missing", 0.0, ""
