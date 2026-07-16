"""本模块提供文本归一、相似度、集合覆盖、区间计算和证据强度等基础函数。"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import date
from typing import Iterable, List, Sequence


STOPWORDS = {
    "and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "is", "are",
    "及", "与", "和", "或", "的", "了", "在", "有", "负责", "相关", "以上", "能够", "具备", "优先",
}

CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CHINESE_YEAR_TOKEN = r"[零〇一二两三四五六七八九十百]+"


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def key_text(value: object) -> str:
    text = normalize_text(value).casefold()
    return re.sub(r"[\s_\-./·•,，:：;；()（）\[\]【】]+", "", text)


def tokenize(value: object) -> List[str]:
    text = normalize_text(value).casefold()
    latin = re.findall(r"[a-z][a-z0-9+#.\-]{1,30}|\d+(?:\.\d+)?", text)
    cjk_runs = re.findall(r"[\u3400-\u9fff]{2,}", text)
    cjk: List[str] = []
    for run in cjk_runs:
        if len(run) <= 4:
            cjk.append(run)
        cjk.extend(run[i:i + 2] for i in range(len(run) - 1))
    return [token for token in latin + cjk if token not in STOPWORDS]


def weighted_overlap(left: object, right: object) -> float:
    a, b = Counter(tokenize(left)), Counter(tokenize(right))
    if not a or not b:
        return 0.0
    common = sum(min(a[k], b[k]) for k in a.keys() & b.keys())
    precision = common / max(1, sum(a.values()))
    recall = common / max(1, sum(b.values()))
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def list_overlap(left: Sequence[object], right: Sequence[object]) -> float | None:
    if not left or not right:
        return None
    a = {key_text(x) for x in left if key_text(x)}
    b = {key_text(x) for x in right if key_text(x)}
    if not a or not b:
        return None
    exact = len(a & b) / len(b)
    substring = 1.0 if any(x in y or y in x for x in a for y in b) else 0.0
    fuzzy = max((weighted_overlap(x, y) for x in left for y in right), default=0.0)
    return min(1.0, max(exact, substring, fuzzy))


def compact_snippet(text: object, needle: object = "", limit: int = 140) -> str:
    source = normalize_text(text).replace("\n", " ")
    if not source:
        return ""
    target = normalize_text(needle).casefold()
    index = source.casefold().find(target) if target else -1
    start = max(0, index - limit // 3) if index >= 0 else 0
    snippet = source[start:start + limit].strip()
    return snippet + ("…" if start + limit < len(source) else "")


def _chinese_number_value(token: str) -> float | None:
    """把常见中文整数转换为数字，年限场景仅接受0到99。"""
    source = normalize_text(token)
    if not source:
        return None
    if all(char in CHINESE_DIGITS for char in source):
        digits = "".join(str(CHINESE_DIGITS[char]) for char in source)
        value = int(digits)
        return float(value) if 0 <= value <= 99 else None
    if "百" in source:
        left, right = source.split("百", 1)
        hundreds = CHINESE_DIGITS.get(left, 1) if left else 1
        remainder = _chinese_number_value(right) if right else 0
        value = hundreds * 100 + (remainder or 0)
        return float(value) if 0 <= value <= 99 else None
    if "十" in source:
        left, right = source.split("十", 1)
        tens = CHINESE_DIGITS.get(left, 1) if left else 1
        ones = CHINESE_DIGITS.get(right, 0) if right else 0
        value = tens * 10 + ones
        return float(value) if 0 <= value <= 99 else None
    return None


def _format_year_number(value: float) -> str:
    """把年限数字格式化为适合继续使用正则解析的短文本。"""
    return str(int(value)) if float(value).is_integer() else str(round(float(value), 2))


def _normalize_chinese_year_numbers(text: str) -> str:
    """只转换紧邻“年”的中文数字，支持一年半、三年以上和三至五年。"""
    source = text

    def replace_range(match: re.Match) -> str:
        low = _chinese_number_value(match.group(1))
        high = _chinese_number_value(match.group(2))
        if low is None or high is None:
            return match.group(0)
        return f"{_format_year_number(low)}-{_format_year_number(high)}年"

    def replace_half(match: re.Match) -> str:
        value = _chinese_number_value(match.group(1))
        return match.group(0) if value is None else f"{_format_year_number(value + 0.5)}年"

    def replace_single(match: re.Match) -> str:
        value = _chinese_number_value(match.group(1))
        return match.group(0) if value is None else f"{_format_year_number(value)}年"

    source = re.sub(
        rf"({CHINESE_YEAR_TOKEN})\s*[-~～—–至到]\s*({CHINESE_YEAR_TOKEN})\s*年",
        replace_range,
        source,
    )
    source = re.sub(rf"({CHINESE_YEAR_TOKEN})\s*年\s*半", replace_half, source)
    source = re.sub(rf"({CHINESE_YEAR_TOKEN})\s*年", replace_single, source)
    return source


def extract_years(text: object) -> float | None:
    """只在明确经验语境中提取年限，忽略毕业、出生、届别和年月日期。"""
    source = _normalize_chinese_year_numbers(normalize_text(text).casefold())
    # 年限范围按保守下限进入标量字段；日期年份为四位数，不会命中此规则。
    source = re.sub(
        r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*[-~～—–至到]\s*(\d{1,2}(?:\.\d+)?)\s*年",
        lambda match: f"{match.group(1)}年",
        source,
    )
    patterns = [
        r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*年\s*(?:(?:及)?以上|\+)?\s*.{0,18}?(?:工作|从业|相关|开发|研发|项目|行业|岗位|实战)?经验",
        r"(?:工作|从业|相关|开发|研发|项目|行业|岗位|实战)?经验(?:年限)?\s*(?::|：|为|约|要求|需|需要|至少|不低于|不少于)?\s*(\d{1,2}(?:\.\d+)?)\s*年?",
        r"(?:从事|拥有|具备|累计)\s*.{0,24}?(?<!\d)(\d{1,2}(?:\.\d+)?)(?!\d)\s*年(?:以上|\+)?(?:.{0,12}?经验)?",
        r"(?:使用|应用|开发|研发|负责)\s*.{0,24}?(?<!\d)(\d{1,2}(?:\.\d+)?)(?!\d)\s*年(?:以上|\+)?",
        r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:work\s+|relevant\s+|professional\s+)?experience",
        r"experience\s*[:：]?\s*(\d{1,2}(?:\.\d+)?)\s*(?:years?|yrs?)?",
    ]
    values: List[float] = []
    for pattern in patterns:
        values.extend(value for item in re.findall(pattern, source, flags=re.I) if 0 <= (value := float(item)) <= 80)
    return max(values) if values else None


def duration_years(experiences: Iterable[object]) -> float | None:
    intervals = []
    today = date.today()
    for item in experiences:
        if not isinstance(item, dict):
            continue
        start = parse_month(item.get("start"))
        end = parse_month(item.get("end")) or (today.year, today.month)
        if start and end and start <= end:
            intervals.append((start[0] * 12 + start[1], end[0] * 12 + end[1]))
    if not intervals:
        return None
    months = set()
    for start, end in intervals:
        months.update(range(start, end + 1))
    return round(len(months) / 12.0, 1)


def parse_month(value: object):
    text = normalize_text(value).casefold()
    if text in {"present", "current", "至今", "现在", "now"}:
        today = date.today()
        return today.year, today.month
    match = re.search(r"(19\d{2}|20\d{2})(?:[-/.年](0?[1-9]|1[0-2]))?", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 1)


def safe_mean(values: Iterable[float], default: float = 0.5) -> float:
    values = list(values)
    return sum(values) / len(values) if values else default


def harmonic(values: Sequence[float], weights: Sequence[float]) -> float:
    if not values or any(v <= 0 for v in values):
        return 0.0
    denominator = sum(w / v for v, w in zip(values, weights))
    return sum(weights) / denominator if denominator else 0.0


def quantified_evidence(text: object) -> float:
    source = normalize_text(text)
    if not source:
        return 0.0
    score = 0.35
    if re.search(r"\d+(?:\.\d+)?\s*(?:%|％|万|亿|k|m|人|个|天|月|年)", source, re.I):
        score += 0.35
    if re.search(r"提升|降低|增长|节省|上线|交付|主导|负责|improv|reduc|increas|launch|deliver|led", source, re.I):
        score += 0.2
    if len(source) >= 35:
        score += 0.1
    return min(1.0, score)
