"""本模块识别并脱敏姓名、联系方式、证件号和地址等个人信息。"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


PATTERNS = {
    "name": re.compile(r"(?i)(?:(?:候选人姓名|姓名)\s*[:：]\s*[\u4e00-\u9fff·]{2,8}|(?:candidate\s*name|full\s*name)\s*[:：]\s*[A-Za-z][A-Za-z .'-]{1,39})"),
    "address": re.compile(r"(?i)(?:详细地址|居住地址|联系地址|住址|地址|address)\s*[:：]\s*.{6,120}?(?=\s*(?:姓名|邮箱|电子邮件|手机|电话|身份证|证件号|微信|QQ|email|phone|mobile|national\s*id|$))"),
    "email": re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)"),
    "phone": re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)|(?<!\w)\+\d{1,3}(?:[- ]?\d){7,12}(?!\d)|(?<!\d)\d{3,4}[- ]\d{7,8}(?!\d)"),
    "national_id": re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\w)"),
    "wechat": re.compile(r"(?i)(微信|wechat|wx)\s*[:：]?\s*[A-Za-z][-_A-Za-z0-9]{5,19}"),
    "qq": re.compile(r"(?i)(qq)\s*[:：]?\s*[1-9]\d{4,11}"),
    "account": re.compile(r"(?i)(?:账号|账户|用户名|account|username)\s*[:：]\s*[-_A-Za-z0-9.]{3,64}"),
}

STRUCTURED_NAME_KEYS = {"candidate_name", "full_name", "姓名", "候选人姓名"}
STRUCTURED_ADDRESS_KEYS = {"address", "home_address", "residential_address", "详细地址", "住址", "居住地址"}
STRUCTURED_ACCOUNT_KEYS = {"account", "account_id", "username", "账号", "账户", "用户名"}


def redact(text: str) -> Tuple[str, Dict[str, int]]:
    result = str(text or "")
    counts: Dict[str, int] = {}
    for name, pattern in PATTERNS.items():
        result, count = pattern.subn(f"[REDACTED_{name.upper()}]", result)
        counts[name] = count
    return result, counts


def redact_object(value: Any) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in STRUCTURED_NAME_KEYS and item not in (None, ""):
                output[key] = "[REDACTED_NAME]"
            elif normalized in STRUCTURED_ADDRESS_KEYS and item not in (None, ""):
                output[key] = "[REDACTED_ADDRESS]"
            elif normalized in STRUCTURED_ACCOUNT_KEYS and item not in (None, ""):
                output[key] = "[REDACTED_ACCOUNT]"
            else:
                output[key] = redact_object(item)
        return output
    if isinstance(value, list):
        return [redact_object(item) for item in value]
    if isinstance(value, tuple):
        return [redact_object(item) for item in value]
    if isinstance(value, str):
        return redact(value)[0]
    return value
