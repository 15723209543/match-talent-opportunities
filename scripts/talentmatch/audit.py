"""本模块检查最终匹配结果的结构、分值范围、隐私信息和必要风险提示。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .privacy import PATTERNS


def audit_output(result: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    scores = result.get("scores", {})
    status = scores.get("status")
    for key in ("overall", "recruiter", "candidate", "provisional_overall", "provisional_recruiter", "provisional_candidate"):
        value = scores.get(key)
        if value is not None and (not isinstance(value, (int, float)) or value < 0 or value > 100):
            errors.append(f"score_out_of_range:{key}")
    if status == "ready_for_review" and scores.get("overall") is None:
        errors.append("formal_score_missing_for_ready_result")
    if status in {"insufficient_data", "hard_requirement_unverified", "hard_failure"} and scores.get("overall") is not None:
        errors.append("formal_score_present_for_noncomparable_result")
    provisional = scores.get("provisional_overall")
    if any(gate.get("status") == "fail" for gate in result.get("gates", [])) and provisional is not None and provisional > 49:
        errors.append("hard_failure_cap_not_applied")
    if result.get("confidence", {}).get("score", -1) < 0 or result.get("confidence", {}).get("score", 101) > 100:
        errors.append("confidence_out_of_range")
    serialized = json.dumps(result, ensure_ascii=False)
    for name, pattern in PATTERNS.items():
        if pattern.search(serialized):
            errors.append(f"pii_detected:{name}")
    if not result.get("method", {}).get("human_review_required"):
        warnings.append("human_review_notice_missing")
    if not result.get("evidence_matrix"):
        warnings.append("evidence_matrix_empty")
    return {"ok": not errors, "errors": errors, "warnings": warnings}
