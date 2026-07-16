#!/usr/bin/env python3
"""本文件执行单名候选人与单个岗位的通用匹配并按需生成报告。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import sys

from talentmatch.audit import audit_output
from talentmatch.engine import match_pair
from talentmatch.io import InputError, load_source, write_json
from talentmatch.persona_reporting import write_persona_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Explainable bidirectional candidate-job matching")
    candidate_group = parser.add_mutually_exclusive_group(required=True)
    candidate_group.add_argument("--candidate", help="Candidate file")
    candidate_group.add_argument("--candidate-text", help="Literal candidate text")
    job_group = parser.add_mutually_exclusive_group(required=True)
    job_group.add_argument("--job", help="Job file")
    job_group.add_argument("--job-text", help="Literal job text")
    parser.add_argument("--metrics", "--weights", dest="metrics", help="自定义匹配指标 Excel；默认读取 reference_indicators/talent_matching_indicators.xlsx")
    parser.add_argument("--as-of-date", help="评分基准日，格式YYYY-MM-DD；用于结果复现")
    parser.add_argument("--output", help="Result JSON path; stdout when omitted")
    parser.add_argument("--markdown", help="兼容参数：生成带SVG图表的Markdown报告")
    parser.add_argument("--report", help="生成角色化Markdown/HTML/文本报告")
    parser.add_argument("--persona", choices=["hr", "candidate", "interviewer", "talent_manager"], default="hr", help="报告受众")
    parser.add_argument("--format", choices=["auto", "markdown", "html", "text", "json"], default="auto", help="报告格式")
    parser.add_argument("--charts-dir", help="SVG图表输出目录")
    args = parser.parse_args()
    try:
        candidate = load_source(args.candidate_text, literal=True) if args.candidate_text is not None else load_source(args.candidate)
        job = load_source(args.job_text, literal=True) if args.job_text is not None else load_source(args.job)
        if isinstance(candidate, list):
            if len(candidate) != 1:
                raise ValueError("Single-pair match expects exactly one candidate record; use batch_match.py for multiple rows.")
            candidate = candidate[0]
        if isinstance(job, list):
            if len(job) != 1:
                raise ValueError("Single-pair match expects exactly one job record; use batch_match.py for multiple rows.")
            job = job[0]
        result = match_pair(candidate, job, args.metrics, as_of_date=args.as_of_date)
        audit = audit_output(result)
        if not audit["ok"]:
            print("Output audit failed: " + ", ".join(audit["errors"]), file=sys.stderr)
            return 4
        write_json(result, args.output)
        report_path = args.report or args.markdown
        if report_path:
            write_persona_report(result, args.persona, report_path, args.format, args.charts_dir)
        return 0
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Internal error: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
