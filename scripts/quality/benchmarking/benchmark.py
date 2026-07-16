#!/usr/bin/env python3
"""本文件重复运行匹配流程并统计耗时，用于检查性能和响应稳定性。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import argparse
import json
import statistics
import time

from talentmatch.engine import match_pair
from talentmatch.excel_config import load_metric_config
from talentmatch.io import load_source


_skill_root = _scripts_dir.parent
BASE_CANDIDATE = load_source(_skill_root / "assets" / "examples" / "candidate.json")
BASE_JOB = load_source(_skill_root / "assets" / "examples" / "job.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure local deterministic matching latency")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--as-of-date", default="2026-07-15", help="固定评分基准日，避免跨日结果漂移")
    args = parser.parse_args()
    iterations = max(1, min(args.iterations, 10000))

    config_start = time.perf_counter()
    config = load_metric_config()
    config_load_ms = (time.perf_counter() - config_start) * 1000
    # 先预热解析器和字体/正则等一次性路径；正式计时采用交错顺序，减少CPU升频、温度和后台负载带来的先后偏差。
    for _ in range(3):
        match_pair(BASE_CANDIDATE, BASE_JOB, config=config, as_of_date=args.as_of_date)
        match_pair(BASE_CANDIDATE, BASE_JOB, as_of_date=args.as_of_date)

    cold_samples = []
    warm_samples = []

    def measure(active_config):
        """测量一次请求；None表示本次请求重新读取Excel。"""
        start = time.perf_counter()
        match_pair(BASE_CANDIDATE, BASE_JOB, config=active_config, as_of_date=args.as_of_date)
        return (time.perf_counter() - start) * 1000

    for index in range(iterations):
        if index % 2 == 0:
            cold_samples.append(measure(None))
            warm_samples.append(measure(config))
        else:
            warm_samples.append(measure(config))
            cold_samples.append(measure(None))

    def summary(samples):
        """返回一组耗时的均值、中位数和P95。"""
        return {
            "mean_ms": round(statistics.mean(samples), 3),
            "median_ms": round(statistics.median(samples), 3),
            "p95_ms": round(sorted(samples)[max(0, int(iterations * 0.95) - 1)], 3),
        }

    cold = summary(cold_samples)
    warm = summary(warm_samples)
    output = {
        "iterations_per_mode": iterations,
        "as_of_date": args.as_of_date,
        "cold_request_with_excel_read": cold,
        "warm_request_with_preloaded_config": warm,
        "excel_config_load_ms": round(config_load_ms, 3),
        "measurement_order": "alternating_after_three_warmups",
        "mean_ms": cold["mean_ms"],
        "p95_ms": cold["p95_ms"],
        "network_calls": 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
