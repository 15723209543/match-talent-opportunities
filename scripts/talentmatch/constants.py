"""本模块集中定义角色、数据充分性、批量规模和评分状态等全局规则。"""

from __future__ import annotations

from typing import Final


PERSONAS: Final[frozenset[str]] = frozenset({"hr", "candidate", "interviewer", "talent_manager"})
SCORE_STATUSES: Final[frozenset[str]] = frozenset({
    "ready_for_review",
    "insufficient_data",
    "hard_requirement_unverified",
    "hard_failure",
    "not_applicable",
})

# 一侧至少要有三项已知指标，且已知指标系数需覆盖该侧可评估系数的20%。
MIN_KNOWN_METRICS: Final[int] = 3
MIN_KNOWN_WEIGHT_RATE: Final[float] = 0.20
MIN_COMPARABLE_CONFIDENCE: Final[float] = 60.0

# 防止一次本地服务请求无界占用内存与CPU。
MAX_BATCH_ITEMS: Final[int] = 100
MAX_MATRIX_PAIRS: Final[int] = 2500


def validate_persona(value: object) -> str:
    """规范化角色名称，并在角色不受支持时给出稳定错误。"""
    persona = str(value or "").strip().casefold()
    if persona not in PERSONAS:
        allowed = ", ".join(sorted(PERSONAS))
        raise ValueError(f"不支持的角色：{value!s}；可选值：{allowed}")
    return persona
