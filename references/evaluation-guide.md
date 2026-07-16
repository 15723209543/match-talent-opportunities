# 真实评测与消融实验指南

自动回归测试只能证明程序按设计运行，不能证明它比关键词匹配更准确。准确率必须来自匿名真实数据、清楚的标注规则和独立人工评审。本项目提供评测工具，但不附带伪造的“真实准确率”。

## 建议的数据规模和角色

- 先用20—30组做标注试运行，统一标准后再扩展到100—300组。
- 每组至少包含一名候选人、两个或以上岗位，以及每个岗位0—3级相关性。
- 至少三名熟悉招聘或目标岗位的评审者独立标注，不先看系统排序。
- 数据必须匿名化，并记录样本来源、授权、去标识方法、岗位族和数据时间。

## JSONL基础格式

每行是一组查询。下面用于说明记录结构；运行 `full` 时还要按后文补齐双向资料与证据：

```json
{"query_id":"q-001","candidate":{"id":"c-001","skills":[{"name":"Python"}],"preferred_locations":["上海"],"preferred_work_modes":["hybrid"],"salary_expectation":{"min":18000,"max":24000,"period":"month"}},"jobs":[{"id":"j-python","required_skills":[{"name":"Python"}],"location":"上海","work_modes":["hybrid"],"salary_range":{"min":18000,"max":26000,"period":"month"}},{"id":"j-java","required_skills":[{"name":"Java"}],"location":"北京","work_modes":["onsite"],"salary_range":{"min":15000,"max":20000,"period":"month"}}],"relevance":{"j-python":3,"j-java":0},"human_reviews":[{"reviewer_id":"r1","recommended_job_id":"j-python"},{"reviewer_id":"r2","recommended_job_id":"j-python"},{"reviewer_id":"r3","recommended_job_id":"j-python"}]}
```

可选的 `protected_variants` 只改变不应参与评分的受保护属性，用于检查结果不变性。真实个人受保护信息不应为了测试而额外收集，可以使用合成变体。

`full` 模式要求每个非硬条件失败的岗位都具备足以形成正式双向分的候选人偏好与岗位条件。资料不足时该条记录会进入失败清单，而不是把空值当成0分参与排序。只有技能资料的样本可用于 `keyword`、`skill_experience` 或 `recruiter_only`，不能据此宣称完成了双向评测。

## 四组消融

| 模式 | 说明 |
|---|---|
| `keyword` | 仅做文本关键词重合，作为基础线 |
| `skill_experience` | 只看技能覆盖与总经验 |
| `recruiter_only` | 使用企业侧适配，不考虑岗位对个人的适配 |
| `full` | 完整双向、证据、置信度和Excel权重方案 |

```bash
python scripts/quality/evaluation/prepare_annotation_pack.py --dataset evaluation.jsonl --reviewers 3 --output annotation-pack.json
python scripts/quality/evaluation/evaluate_dataset.py --dataset evaluation.jsonl --mode full --top-k 5 --output evaluation-result.json
python scripts/quality/evaluation/run_ablation.py --dataset evaluation.jsonl --top-k 5 --output ablation-result.json
```

## 输出指标

- Top-K命中率：前K个结果是否包含人工认为相关的岗位。
- NDCG@K：高相关岗位是否排在更前面。
- 排序一致性：系统成对排序与人工相关性顺序的一致程度。
- 人工决策一致性：系统第一名与多名评审多数推荐的一致率。
- 失败处理率：有格式问题的样本不会让整个评测中止。
- 受保护属性分数变化：只改受保护属性后，分数差应为0或处于事先定义的极小容差内。

报告结果时应同时给样本量、岗位族分布、标注者一致性、置信区间、失败样本和限制。不要只报一个最高数字，也不要把合成演示集写成真实业务效果。
