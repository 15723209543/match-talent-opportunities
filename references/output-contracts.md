# 输出里有什么

同一份匹配结果可以写成JSON、Markdown、HTML或纯文本。四种格式使用相同的底层结果，但会根据HR、求职者、面试官和人才发展负责人的任务重新安排内容。

## 先看处理状态

`scores.status` 有四种主要值：

| 状态 | 含义 | 是否参与正式排序 |
|---|---|---|
| `ready_for_review` | 双侧数据充分、置信度达到60且没有明确硬性失败 | 可以，但仍需人工复核 |
| `insufficient_data` | 资料或证据不足 | 不可以，先补资料 |
| `hard_requirement_unverified` | 至少一个硬条件因资料缺失而无法确认 | 不可以，先核验硬条件 |
| `hard_failure` | 至少一个明确标记为硬性的条件不满足 | 不可以，先人工确认条件是否必要且事实是否准确 |

`overall` 只有在 `ready_for_review` 时才有值。`provisional_overall` 是完整JSON和审计记录中的诊断值，不能用于正式排名、录用或淘汰。角色JSON的 `headline`、Markdown、HTML和SVG总览不会突出暂估值；状态不满足时统一显示“暂不可比较”。

批量接口把结果拆成 `ready_for_review`、`needs_more_data`、`unverified_hard_requirements`、`hard_failures` 四组。只有第一组有连续的 `rank`。

## 完整JSON

完整JSON包含：

- `meta`：引擎、版本、候选人和岗位ID。
- `scoring_context`：评分基准日和“原始输入审计、净化副本评分”的数据流说明。
- `scores`：状态、正式分、暂估分、双侧数据充分性和两位小数规则。
- `confidence`：候选人完整度、岗位完整度、证据覆盖、可评分系数覆盖和解析确定性。
- `gates`：硬条件的 `pass`、`fail`、`unknown` 三态结果；未明确斜杠语义的硬条件以 `ambiguous_requirement_needs_confirmation` 说明待核验原因。
- `recruiter_dimensions` 与 `candidate_dimensions`：80项指标的分数、系数、贡献、状态和 `evidence_refs`。
- `evidence_matrix`：技能和职责的匹配事实。
- `fairness_audit`、`warnings`：受保护条件、嵌入指令风险，以及 `ambiguous_slash_requirement_requires_confirmation` 等解析确认提示。
- `recommendations`：明确差距、待补证据、面试问题、简历动作和发展计划。
- `analytics`：类别画像、主要驱动、完整度、HHI和敏感性情景。
- `method`：Excel路径、SHA-256、指标数、岗位权重模板、覆盖项数量和阈值。

每个 `evidence_refs` 都说明来源是候选人还是岗位、原始字段路径、简短片段、A/B/C证据等级和 `verified:false`。A表示信息更具体，不代表真实性已经核验。

## 四类角色JSON

- HR：`hard_conditions`、`high_confidence_evidence`、`priority_verification`、`candidate_constraints`、`manual_review_queue_reasons`。
- 求职者：`my_evidence_strengths`、`job_conditions_to_confirm`、`questions_for_employer`、`resume_actions`、`interview_preparation`、`development_plan`。
- 面试官：`opening_checks`、`evidence_probes`、`follow_up_conditions`、`scorecard_dimensions`、`recording_areas`、`prohibited_topics`、`recording_rule`。
- 人才发展负责人：`target_role_readiness`、`capability_matrix`、`capability_gaps`、`evidence_needed`、`development_priorities`、`success_evidence`。

角色结果始终保留 `full_match`，方便审计和二次处理。无效角色会直接报错，不会静默套用HR模板。

## 图文文件

- Markdown使用表格、列表和相对图片链接，图表放在 `<报告名>_assets/`。角色报告与 `scripts/io_tools/export/export_markdown.py` 兼容入口复用同一组安全文本、表格和列表渲染函数；候选人和岗位ID、摘要、条件、指标名、问题、证据、建议、行动项及计划中的动态值会统一转为纯文本，输入自带的HTML标签、图片、链接、换行、反斜杠和 `= + - @` 前缀不能生成新的报告节点。
- HTML是UTF-8离线单页，不加载外部脚本、CDN或字体。
- 纯文本适合日志、邮件草稿和不支持富文本的系统。

每份完整报告包含五张SVG：双向总览、角色类别画像、主要贡献、数据完整度和优先核验。资料不足时，总览分数显示 `--` 和“暂不可比较”；类别只有少数指标已知时，类别图也显示 `--`，不会把1/3已知的100分放进柱状图。
