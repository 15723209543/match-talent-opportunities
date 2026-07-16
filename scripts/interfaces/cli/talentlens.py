#!/usr/bin/env python3
"""本文件提供统一命令行入口，供终端、持续集成和可执行本地命令的平台调用。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(_scripts_dir))

from talentmatch.batch import triage_candidates, triage_jobs
from talentmatch.engine import match_pair
from talentmatch.excel_config import load_metric_config, validate_metric_config
from talentmatch.io import load_collection, load_source, write_json
from talentmatch.persona_reporting import build_persona_payload, write_persona_report


PROFILE_CHOICES = ["general", "software_engineering", "product_operations", "sales_customer"]


def main() -> int:
    parser = argparse.ArgumentParser(description="TalentLens跨平台统一命令行")
    sub = parser.add_subparsers(dest="command", required=True)
    match_cmd = sub.add_parser("match", help="单候选人与单岗位双向匹配")
    match_cmd.add_argument("--candidate", required=True)
    match_cmd.add_argument("--job", required=True)
    match_cmd.add_argument("--metrics")
    match_cmd.add_argument("--profile", choices=PROFILE_CHOICES, default="general", help="岗位权重模板")
    match_cmd.add_argument("--as-of-date", help="评分基准日，格式YYYY-MM-DD；用于结果复现")
    match_cmd.add_argument("--persona", choices=["hr", "candidate", "interviewer", "talent_manager"], default="hr")
    match_cmd.add_argument("--format", choices=["json", "markdown", "html", "text"], default="json")
    match_cmd.add_argument("--output")
    match_cmd.add_argument("--charts-dir")
    rank_c = sub.add_parser("rank-candidates", help="同一岗位候选人排序")
    rank_c.add_argument("--candidates", required=True)
    rank_c.add_argument("--job", required=True)
    rank_c.add_argument("--metrics")
    rank_c.add_argument("--profile", choices=PROFILE_CHOICES, default="general")
    rank_c.add_argument("--as-of-date", help="评分基准日，格式YYYY-MM-DD")
    rank_c.add_argument("--output")
    rank_j = sub.add_parser("rank-jobs", help="同一求职者岗位排序")
    rank_j.add_argument("--candidate", required=True)
    rank_j.add_argument("--jobs", required=True)
    rank_j.add_argument("--metrics")
    rank_j.add_argument("--profile", choices=PROFILE_CHOICES, default="general")
    rank_j.add_argument("--as-of-date", help="评分基准日，格式YYYY-MM-DD")
    rank_j.add_argument("--output")
    validate = sub.add_parser("validate-metrics", help="校验80项Excel指标表")
    validate.add_argument("--metrics")
    validate.add_argument("--profile", choices=PROFILE_CHOICES, default="general")
    args = parser.parse_args()
    try:
        if args.command == "match":
            result = match_pair(load_source(args.candidate), load_source(args.job), args.metrics, profile=args.profile, as_of_date=args.as_of_date)
            if args.format == "json":
                write_json(build_persona_payload(result, args.persona), args.output)
            else:
                if not args.output:
                    raise ValueError("Markdown、HTML或文本报告必须指定 --output")
                write_persona_report(result, args.persona, args.output, args.format, args.charts_dir)
        elif args.command == "rank-candidates":
            write_json(triage_candidates(load_collection(args.candidates), load_source(args.job), args.metrics, args.profile, args.as_of_date), args.output)
        elif args.command == "rank-jobs":
            write_json(triage_jobs(load_source(args.candidate), load_collection(args.jobs), args.metrics, args.profile, args.as_of_date), args.output)
        else:
            errors = validate_metric_config(args.metrics, args.profile)
            config = load_metric_config(args.metrics, args.profile) if not errors else None
            write_json({"ok": not errors, "errors": errors, "metric_count": config["metric_count"] if config else 0, "source": config["source"] if config else args.metrics, "profile": config.get("profile") if config else args.profile, "available_profiles": config.get("available_profiles", []) if config else []}, None)
            return 0 if not errors else 4
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
