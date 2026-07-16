#!/usr/bin/env python3
"""本脚本用可复现的随机中文简历与岗位片段压力测试解析和匹配流程，统计未捕获异常。"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.engine import match_pair
from talentmatch.parser import parse_candidate, parse_job


CANDIDATE_FRAGMENTS = [
    "教育经历：2025年9月-2029年6月，本科",
    "2022年7月毕业，拥有3年Python开发经验",
    "拥有三年Python开发经验",
    "具备一年半数据分析经验",
    "从事Java开发两年左右",
    "具有三至五年项目经验",
    "从事Go后端开发2.5年",
    "使用Java开发订单系统3年，熟悉MySQL",
    "不接受远程办公，期望现场办公",
    "接受混合办公，但暂不考虑完全远程",
    "期望薪资1.5w-2w/月",
    "期望薪资不低于8k",
    "期望薪资10k以内",
    "项目经历：使用Python、FastAPI开发课程系统",
    "2025届，出生于2003年",
    "I have 4 years of experience in data products.",
    "\u0000\t  任意空白和控制字符  ",
    "" * 0,
]

JOB_FRAGMENTS = [
    "任职要求：必须掌握Java或Go，熟悉MySQL",
    "Python、FastAPI 或 Django",
    "Java、Go、Python中至少一种",
    "要求3年以上工作经验",
    "要求三年以上Python开发经验",
    "必须具备2.5年相关经验",
    "必须掌握SQL，3年工作经验",
    "以下条件均为必须：本科，Java或Go",
    "以下条件均为必须：\n- Java\n- MySQL",
    "以下条件优先：\n- Redis\n- Docker",
    "熟悉Java/Go",
    "Java/Go任选一种",
    "本岗位暂不支持远程办公，仅现场办公",
    "支持混合办公，不提供完全远程",
    "薪资1.5w-2w/月，13薪",
    "薪资15k-20k·13-15薪",
    "薪资8k以上，具体面议",
    "工作地点：上海",
    "Go to market experience is preferred.",
    "\u0000\t  未知字段：???  ",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="随机中文自然语言鲁棒性测试")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()
    randomizer = random.Random(args.seed)
    failures = []
    statuses: dict[str, int] = {}
    for index in range(max(1, args.iterations)):
        candidate_text = "\n".join(randomizer.sample(CANDIDATE_FRAGMENTS, randomizer.randint(1, 6)))
        job_text = "\n".join(randomizer.sample(JOB_FRAGMENTS, randomizer.randint(1, 6)))
        try:
            result = match_pair(parse_candidate(candidate_text), parse_job(job_text))
            status = str(result.get("scores", {}).get("status", "unknown"))
            statuses[status] = statuses.get(status, 0) + 1
        except Exception as exc:  # 本脚本的目的就是记录任何越过公共入口的未捕获异常
            failures.append({
                "case": index,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "candidate": candidate_text[:500],
                "job": job_text[:500],
            })
    payload = {
        "ok": not failures,
        "iterations": max(1, args.iterations),
        "seed": args.seed,
        "uncaught_failures": len(failures),
        "status_counts": statuses,
        "failure_examples": failures[:10],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 4


if __name__ == "__main__":
    raise SystemExit(main())
