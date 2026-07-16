#!/usr/bin/env python3
"""本文件提供逐行JSON标准输入输出协议，供编辑器、桌面应用和长期子进程调用。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.batch import triage_candidates, triage_jobs
from talentmatch.engine import match_pair
from talentmatch.persona_reporting import build_persona_payload


MAX_LINE_BYTES = 2 * 1024 * 1024
PROFILE_CHOICES = {"general", "software_engineering", "product_operations", "sales_customer"}


def handle(request: dict, metrics_path: str | None = None) -> dict:
    """处理一条请求；指标文件只能由进程启动参数决定。"""
    if not isinstance(request, dict):
        raise ValueError("每行必须是JSON对象")
    operation = request.get("operation", "match")
    if request.get("metrics") not in (None, ""):
        raise ValueError("请求不能指定指标文件；请在启动进程时使用 --metrics 配置")
    profile = str(request.get("profile") or "general")
    if profile not in PROFILE_CHOICES:
        raise ValueError("不支持的岗位权重模板：" + profile)
    if operation == "health":
        return {"status": "ok", "protocol": "TalentLens-NDJSON/1", "metric_count": 80, "profiles": sorted(PROFILE_CHOICES)}
    if operation == "match":
        result = match_pair(
            request.get("candidate"),
            request.get("job"),
            metrics_path,
            profile=profile,
            as_of_date=request.get("as_of_date"),
        )
        audience = request.get("audience", "hr")
        return build_persona_payload(result, audience) if request.get("persona_view", True) else result
    if operation == "rank_candidates":
        candidates = request.get("candidates")
        if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
            raise ValueError("candidates必须是由JSON对象组成的数组")
        return triage_candidates(candidates, request.get("job"), metrics_path, profile, request.get("as_of_date"))
    if operation == "rank_jobs":
        jobs = request.get("jobs")
        if not isinstance(jobs, list) or not all(isinstance(item, dict) for item in jobs):
            raise ValueError("jobs必须是由JSON对象组成的数组")
        return triage_jobs(request.get("candidate"), jobs, metrics_path, profile, request.get("as_of_date"))
    raise ValueError(f"不支持的operation：{operation}")


def main() -> int:
    parser = argparse.ArgumentParser(description="TalentLens逐行JSON标准输入输出服务")
    parser.add_argument("--metrics", help="进程固定使用的匹配指标Excel；单条请求不能覆盖")
    args = parser.parse_args()
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_LINE_BYTES:
            response = {"ok": False, "error": "request_line_too_large"}
        else:
            try:
                request = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(request, dict):
                    raise ValueError("每行必须是JSON对象")
                response = {"ok": True, "request_id": request.get("request_id"), "result": handle(request, args.metrics)}
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                response = {"ok": False, "error": str(exc)}
        # Keep the line protocol ASCII-safe so PowerShell/cmd and Unix pipes decode identically.
        print(json.dumps(response, ensure_ascii=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
