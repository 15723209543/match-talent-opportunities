#!/usr/bin/env python3
"""本文件提供本地HTTP JSON服务，供工作流平台、后端服务和远程工具接入。"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.batch import triage_candidates, triage_jobs
from talentmatch.engine import match_pair
from talentmatch.excel_config import load_metric_config
from talentmatch.persona_reporting import build_persona_payload


MAX_BODY_BYTES = 2 * 1024 * 1024
PROFILE_CHOICES = {"general", "software_engineering", "product_operations", "sales_customer"}


class RequestValidationError(ValueError):
    """携带稳定错误码的HTTP请求结构错误。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_request_payload(path: str, request: Any) -> dict:
    """在业务代码读取字段前验证顶层对象与批量数组结构。"""
    if not isinstance(request, dict):
        raise RequestValidationError("invalid_json_object", "请求体顶层必须是JSON对象")
    if path == "/rank-candidates":
        candidates = request.get("candidates")
        if not isinstance(candidates, list):
            raise RequestValidationError("candidates_must_be_array", "candidates必须是JSON数组")
        if not all(isinstance(item, dict) for item in candidates):
            raise RequestValidationError("candidate_must_be_object", "每个候选人必须是JSON对象")
    elif path == "/rank-jobs":
        jobs = request.get("jobs")
        if not isinstance(jobs, list):
            raise RequestValidationError("jobs_must_be_array", "jobs必须是JSON数组")
        if not all(isinstance(item, dict) for item in jobs):
            raise RequestValidationError("job_must_be_object", "每个岗位必须是JSON对象")
    return request


class Handler(BaseHTTPRequestHandler):
    server_version = "TalentLensHTTP/2.0"

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "TalentLens", "metric_count": 80, "profiles": sorted(PROFILE_CHOICES), "network_outbound": False})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("请求体必须在1字节至2MB之间")
            request = validate_request_payload(
                self.path,
                json.loads(self.rfile.read(length).decode("utf-8-sig")),
            )
            if request.get("metrics") not in (None, ""):
                raise ValueError("HTTP请求不能指定指标文件；请在服务启动时使用 --metrics 配置")
            metrics = getattr(self.server, "metrics_path", None)
            profile = str(request.get("profile") or "general")
            if profile not in PROFILE_CHOICES:
                raise ValueError("不支持的岗位权重模板：" + profile)
            if self.path == "/match":
                result = match_pair(
                    request.get("candidate"),
                    request.get("job"),
                    metrics,
                    profile=profile,
                    as_of_date=request.get("as_of_date"),
                )
                audience = request.get("audience", "hr")
                payload = build_persona_payload(result, audience) if request.get("persona_view", True) else result
            elif self.path == "/rank-candidates":
                payload = triage_candidates(request.get("candidates", []), request.get("job"), metrics, profile, request.get("as_of_date"))
            elif self.path == "/rank-jobs":
                payload = triage_jobs(request.get("candidate"), request.get("jobs", []), metrics, profile, request.get("as_of_date"))
            else:
                self._send(404, {"error": "not_found"})
                return
            self._send(200, {"ok": True, "request_id": request.get("request_id"), "result": payload})
        except RequestValidationError as exc:
            self._send(400, {"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        except json.JSONDecodeError as exc:
            self._send(400, {"ok": False, "error": {"code": "invalid_json", "message": str(exc)}})
        except (ValueError, TypeError) as exc:
            self._send(400, {"ok": False, "error": {"code": "invalid_request", "message": str(exc)}})
        except Exception as exc:  # keep the local service alive on unexpected input
            self._send(500, {"ok": False, "error": {"code": "internal_error", "message": type(exc).__name__}})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[TalentLens HTTP] {self.address_string()} {format % args}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="TalentLens本地HTTP JSON服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-remote", action="store_true", help="显式允许绑定非回环地址；生产环境仍应增加网关鉴权")
    parser.add_argument("--metrics", help="服务端固定使用的匹配指标Excel；请求不能覆盖此路径")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote:
        parser.error("绑定非回环地址必须显式添加 --allow-remote")
    load_metric_config(args.metrics)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.metrics_path = args.metrics  # type: ignore[attr-defined]
    print(f"TalentLens listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
