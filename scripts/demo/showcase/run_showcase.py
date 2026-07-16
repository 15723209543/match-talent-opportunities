#!/usr/bin/env python3
"""本文件一键生成四类角色报告、边界案例和批量分流结果，便于演示与评审。"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
SKILL_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.batch import triage_candidates
from talentmatch.engine import match_pair
from talentmatch.io import write_json
from talentmatch.persona_reporting import write_persona_report


def _load_example(name: str) -> dict:
    """读取随项目提供的完整示例。"""
    return json.loads((SKILL_ROOT / "assets" / "examples" / name).read_text(encoding="utf-8"))


def _index(output: Path, result: dict, links: list[tuple[str, str, str]]) -> None:
    """生成不依赖网络资源的演示入口页。"""
    cards = "".join(
        f'<a class="card" href="{html.escape(path)}"><b>{html.escape(title)}</b><span>{html.escape(note)}</span></a>'
        for title, path, note in links
    )
    scores = result["scores"]
    content = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TalentLens 演示中心</title><style>
body{{margin:0;background:#f3f6f9;color:#172b4d;font-family:"Microsoft YaHei",sans-serif}}main{{max-width:1080px;margin:36px auto;padding:0 20px}}header{{padding:32px;background:#243b53;color:white;border-radius:18px}}.score{{font-size:42px;font-weight:800;color:#f2c14e}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:22px}}.card{{display:flex;flex-direction:column;gap:8px;background:white;padding:22px;border-radius:14px;text-decoration:none;color:#172b4d;box-shadow:0 5px 18px #172b4d12;border-top:5px solid #3c78a8}}.card:hover{{transform:translateY(-2px)}}.card span{{color:#64748b}}footer{{margin:24px 0;padding:18px;background:#fff7e6;border-left:5px solid #d8a23a}}
</style></head><body><main><header><h1>TalentLens 双向人岗匹配演示</h1><div class="score">{scores.get("overall"):.2f}</div><p>状态：{html.escape(scores.get("status", ""))}｜置信度：{result.get("confidence", {}).get("score", 0):.2f}</p></header><div class="grid">{cards}</div><footer>正式分只在资料充分、所有硬条件已核验且置信度达标时出现；所有人事结论仍需人工复核。</footer></main></body></html>'''
    (output / "index.html").write_text(content, encoding="utf-8")


def main() -> int:
    """生成完整演示目录并返回入口页路径。"""
    parser = argparse.ArgumentParser(description="一键生成TalentLens四角色图文演示")
    parser.add_argument("--output", default="showcase", help="演示输出目录")
    parser.add_argument("--as-of-date", default="2026-07-15", help="评分基准日，格式YYYY-MM-DD")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    candidate = _load_example("candidate.json")
    job = _load_example("job.json")
    result = match_pair(candidate, job, as_of_date=args.as_of_date)
    write_json(result, output / "full-match.json")

    links: list[tuple[str, str, str]] = []
    titles = {
        "hr": "HR核验报告",
        "candidate": "求职者发展报告",
        "interviewer": "面试官工作单",
        "talent_manager": "人才发展报告",
    }
    for persona, title in titles.items():
        filename = f"{persona}.html"
        write_persona_report(result, persona, output / filename, "html")
        links.append((title, filename, "角色专属排版、内容顺序和五张SVG分析图"))

    insufficient = match_pair({"id": "demo-incomplete"}, {"id": "demo-empty-job"}, as_of_date=args.as_of_date)
    write_json(insufficient, output / "insufficient-data.json")
    write_persona_report(insufficient, "hr", output / "insufficient-data.html", "html")
    links.append(("资料不足案例", "insufficient-data.html", "不产生正式综合分，展示待补资料"))

    comparison_job = json.loads(json.dumps(job, ensure_ascii=False))
    for skill in comparison_job.get("required_skills", []):
        skill["hard"] = False
    triage = triage_candidates([candidate, {"id": "demo-needs-data"}], comparison_job, as_of_date=args.as_of_date)
    write_json(triage, output / "batch-triage.json")
    links.append(("批量分流结果", "batch-triage.json", "可复核、待补资料、硬条件待核验、硬性不符分开输出"))

    unverified_candidate = json.loads(json.dumps(candidate, ensure_ascii=False))
    unverified_candidate.pop("education", None)
    unverified_job = json.loads(json.dumps(job, ensure_ascii=False))
    unverified_job["education"] = {"min_level": "bachelor", "hard": True}
    unverified = match_pair(unverified_candidate, unverified_job, as_of_date=args.as_of_date)
    write_persona_report(unverified, "hr", output / "hard-requirement-unverified.html", "html")
    links.append(("硬条件待核验", "hard-requirement-unverified.html", "未知硬条件阻止正式分和排名，并给出补证方向"))

    protected_job = json.loads(json.dumps(job, ensure_ascii=False))
    protected_job["responsibilities"] = ["限男性，年龄30岁以下，" + str(item) for item in job.get("responsibilities", [])]
    protected_result = match_pair(candidate, protected_job, as_of_date=args.as_of_date)
    invariance = {
        "as_of_date": args.as_of_date,
        "base_provisional_overall": result["scores"]["provisional_overall"],
        "protected_variant_provisional_overall": protected_result["scores"]["provisional_overall"],
        "score_delta": round(float(protected_result["scores"]["provisional_overall"]) - float(result["scores"]["provisional_overall"]), 2),
        "job_fairness_audit": protected_result["fairness_audit"]["job"],
        "conclusion": "敏感条件触发风险警告，但不进入评分副本。",
    }
    write_json(invariance, output / "fairness-invariance.json")
    links.append(("公平性分数不变性", "fairness-invariance.json", "对比原岗位与敏感条件变体，分数差应为0"))

    write_json(result.get("fairness_audit", {}), output / "fairness-audit.json")
    links.append(("公平性审计", "fairness-audit.json", "展示敏感条件与嵌入指令的治理结果"))
    _index(output, result, links)
    print(str(output / "index.html"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
