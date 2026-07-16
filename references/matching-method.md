# 匹配分数是怎样算出来的

## 先读指标表

`reference_indicators/talent_matching_indicators.xlsx` 是唯一的系数配置。A列填写0—10，B列是与代码函数对应的指标ID，D列标明企业侧、求职者侧或综合项，F列控制是否启用，H列决定缺失值怎样处理。

同一工作簿的 `岗位权重模板` 提供四套配置：`general`、`software_engineering`、`product_operations`、`sales_customer`。模板覆盖系数仍限制在0—10；模板没有列出的指标继续使用A列基础系数。结果会记录模板ID、版本、适用岗位和覆盖项数量。

单次匹配读取工作簿一次；一个批量请求也只读取一次。下一次请求会重新读取，因此保存Excel后不必改代码或重启命令行任务。HTTP与NDJSON服务的指标路径只能在进程启动时配置，避免请求任意读取服务器文件。

每一项先得到0—1原始分和 `met`、`partial`、`gap`、`unknown` 或 `not_applicable` 状态，再换算到0—100。没有岗位要求的指标属于 `not_applicable`，既不是100分，也不进入可评估分母。

技能覆盖先按逻辑组计算，再进入指标加权。`all` 组按组内技能共同评价；`any` 组选择得分最高的若干项，数量由 `minimum_match_count` 决定；一个逻辑组只作为一个评分单元，避免“FastAPI或Django”被重复扣分。硬条件核验也按同一组逻辑执行。裸斜杠组会带 `needs_confirmation`；普通评分采用不多要求技能的保守OR，硬条件则保持 `unknown`，直到用户确认斜杠表示AND还是OR。

默认缺失策略是 `exclude`：未知项不进入分母，也不记0。`neutral` 会按50参与暂估，`zero` 会按0参与暂估；不论采用哪种策略，原始未知项都不会被算成已知资料。

## 双侧评分和数据充分性

```text
normalized_weight_i = coefficient_i / sum(valid_coefficients)
side_estimate = sum(effective_metric_score_i × normalized_weight_i)
known_weight_rate = known_raw_metric_coefficients / applicable_coefficients
```

企业侧42项和求职者侧38项分别计算。每一侧至少需要3项原始已知指标，且已知指标系数覆盖率达到20%，才具备单侧可评分条件。

置信度综合候选人资料完整度、岗位资料完整度、证据覆盖、双侧可评分系数覆盖、解析确定性和风险警告。没有证据行时证据覆盖率为0，不用中性值填补。

## 正式综合分

```text
overall = (wr + wc) / (wr / recruiter_score + wc / candidate_score)
```

`wr` 与 `wc` 来自Excel中的两项综合系数。调和平均让较低一侧产生更明显影响，避免单边高分掩盖另一边的不适配。

只有以下条件同时满足才提供 `overall`：

1. 企业侧和求职者侧都具备可评分条件；
2. 置信度不低于60；
3. 没有明确硬性失败；
4. 所有标记为硬性的条件都已核验，不存在 `unknown`。

资料不足时状态为 `insufficient_data`；硬条件无法核验时状态为 `hard_requirement_unverified`；两者都只在完整JSON中保留诊断用 `provisional_overall`，普通报告和SVG总览显示“暂不可比较”。出现明确硬性失败时状态为 `hard_failure`，正式分为空，诊断暂估值最高封顶49.00。硬条件只有 `hard:true` 才能触发；字符串 `"false"` 和 `"0"` 会被正确解析为假，含糊布尔值会报错。

候选人完全没写 `skills` 时，技能指标为 `unknown`。只有 `skills: []` 与 `skills_confirmed_complete: true` 同时出现，空列表才被解释为“已确认没有”，相应指标才能成为 `gap`。

## 证据与分析

每项指标带有 `evidence_refs`，可追溯候选人或岗位字段。证据等级A/B/C只表达具体程度，统一标记 `verified:false`，真实性由人工复核。

结果还提供双侧分差、类别得分、主要贡献、优先补证、80项完整度、证据覆盖、系数集中度HHI和单项系数提高20%的局部敏感性情景。敏感性分析不是因果结论。

评分前先对原始资料执行公平性审计，再用不含受保护字段、敏感短语和嵌入式指令的副本计算指标。警告可以不同，净化前后可用事实相同时，分数必须相同。

结果中的 `scoring_context.as_of_date` 是技能新鲜度等时间指标的统一基准。固定输入、工作簿和基准日应得到相同评分，只有生成时间字段可以变化。任何分数都不能单独决定高影响人事事项。
