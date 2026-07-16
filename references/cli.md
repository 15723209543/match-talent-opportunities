# 常用命令

下面的命令都在 Skill 根目录执行，需要 Python 3.10 或更高版本。核心运行过程只使用标准库。

## 第一次使用

先用内置示例跑一遍，确认环境和指标表都正常：

```bash
python scripts/quality/diagnostics/doctor.py
python scripts/governance/validation/validate_metrics.py
python scripts/interfaces/cli/talentlens.py match --candidate assets/examples/candidate.json --job assets/examples/job.json --profile general --persona hr --format json --as-of-date 2026-07-15
```

统一CLI的 `--persona` 支持 `hr`、`candidate`、`interviewer`、`talent_manager`；`--format` 支持 `json`、`markdown`、`html`、`text`。Markdown、HTML和纯文本需要同时填写 `--output`，图表会写入同名的 `_assets` 目录。

`--profile` 支持 `general`、`software_engineering`、`product_operations`、`sales_customer`。它只接受模板ID，不能接收任意文件路径；自定义工作簿仍通过进程启动参数 `--metrics` 指定。

所有候选人—岗位匹配和排序入口都可追加 `--as-of-date YYYY-MM-DD`。固定基准日后，技能新鲜度等时间相关指标可以复现；省略时使用运行当天并把实际日期写入结果。

## HR常用命令

```bash
python scripts/hr/screening/match_candidate.py --candidate candidate.json --job job.json --format html --output hr-report.html
python scripts/hr/ranking/rank_candidates.py --candidates candidates/ --job job.json
python scripts/hr/ranking/build_shortlist.py --candidates candidates/ --job job.json --top 10
python scripts/hr/ranking/compare_candidates.py --candidates candidates/ --job job.json
python scripts/hr/capability/analyze_capability.py --candidate candidate.json --job job.json
python scripts/hr/evidence/analyze_evidence_quality.py --candidate candidate.json --job job.json
python scripts/hr/screening/generate_screening_questions.py --candidate candidate.json --job job.json
python scripts/hr/analytics/analyze_sensitivity.py --candidate candidate.json --job job.json
```

## 求职者常用命令

```bash
python scripts/candidate/matching/match_job.py --candidate candidate.json --job job.json
python scripts/candidate/reporting/generate_full_report.py --candidate candidate.json --job job.json --format markdown --output my-report.md
python scripts/candidate/opportunities/rank_jobs.py --candidate candidate.json --jobs jobs/
python scripts/candidate/opportunities/compare_offers.py --candidate candidate.json --jobs jobs/
python scripts/candidate/resume/analyze_resume_gap.py --candidate candidate.json --job job.json
python scripts/candidate/interview/prepare_interview.py --candidate candidate.json --job job.json
python scripts/candidate/capability/analyze_capability.py --candidate candidate.json --job job.json
python scripts/candidate/personality/analyze_workstyle_personality.py --candidate candidate.json --job job.json
python scripts/candidate/compensation/analyze_compensation.py --candidate candidate.json --job job.json
```

`candidate/personality/` 只比较用户主动提供的工作风格偏好，不做心理或人格诊断。

## 面试官和人才发展管理者

```bash
python scripts/interviewer/planning/generate_question_plan.py --candidate candidate.json --job job.json
python scripts/interviewer/capability/generate_capability_probes.py --candidate candidate.json --job job.json
python scripts/interviewer/scoring/create_scorecard.py --candidate candidate.json --job job.json
python scripts/interviewer/fairness/audit_bias_risk.py --candidate candidate.json --job job.json
python scripts/talent_manager/mobility/rank_internal_mobility.py --candidate candidate.json --jobs jobs/
python scripts/talent_manager/analytics/build_capability_matrix.py --candidate candidate.json --job job.json
python scripts/talent_manager/development/build_development_plan.py --candidate candidate.json --job job.json
```

## 批量、治理和质量检查

```bash
python scripts/interfaces/cli/talentlens.py rank-candidates --candidates candidates/ --job job.json --output ranking.json
python scripts/interfaces/cli/talentlens.py rank-jobs --candidate candidate.json --jobs jobs/ --output ranking.json
python scripts/workflows/matching/batch_match.py --candidates candidates/ --jobs jobs/ --output matrix.json
python scripts/governance/privacy/redact_pii.py resume.txt --output redacted.txt
python scripts/governance/fairness/audit_fairness.py jd.txt
python scripts/quality/testing/run_all_tests.py
python scripts/quality/testing/fuzz_natural_language.py --iterations 500 --seed 20260715
python scripts/quality/benchmarking/benchmark.py --iterations 100 --as-of-date 2026-07-15
python scripts/demo/showcase/run_showcase.py --output showcase --as-of-date 2026-07-15
python scripts/workflows/evidence/reassess_with_evidence.py --candidate candidate.json --job job.json --output review.json
python scripts/workflows/evidence/reassess_with_evidence.py --candidate candidate.json --job job.json --evidence-update evidence-update.json --output reassessed.json
python scripts/quality/evaluation/prepare_annotation_pack.py --dataset evaluation.jsonl --reviewers 3 --output annotation-pack.json
python scripts/quality/evaluation/evaluate_dataset.py --dataset evaluation.jsonl --mode full --top-k 5 --output evaluation-result.json
python scripts/quality/evaluation/run_ablation.py --dataset evaluation.jsonl --top-k 5 --output ablation-result.json
```

`build_shortlist.py` 为兼容原入口名称而保留，实际输出字段是 `manual_review_queue`，不表示自动推荐或录用。

所有单次CLI匹配和排序入口都可以追加 `--metrics path/to/custom.xlsx`。程序会在这一次调用开始时读取指定工作簿。HTTP与NDJSON只能在服务启动时添加 `--metrics`，请求本身不能传任意路径。
