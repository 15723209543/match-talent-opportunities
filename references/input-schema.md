# 输入资料怎么准备

最推荐的格式是UTF-8 JSON。没有掌握的信息留空或填 `null`，不要为了让分数更完整而补写事实。

## 一个最小可运行示例

```json
{
  "candidate": {
    "id": "c1",
    "target_roles": ["高级数据产品经理"],
    "skills": [{"name": "SQL", "level": 4, "years": 5, "last_used_year": 2026, "evidence": "查询耗时降低42%"}],
    "experience_years": 5,
    "preferred_locations": ["上海"],
    "salary_expectation": {"min": 25000, "max": 32000, "currency": "CNY", "period": "month"}
  },
  "job": {
    "id": "j1",
    "title": "高级数据产品经理",
    "responsibilities": ["规划企业指标平台"],
    "required_skills": [{"name": "SQL", "level": 3, "years": 3, "hard": true, "weight": 2}],
    "min_experience_years": 4,
    "location": "上海",
    "salary_range": {"min": 26000, "max": 35000, "currency": "CNY", "period": "month"}
  }
}
```

实际CLI会分别读取候选人文件和岗位文件，所以文件里不需要再套最外层的 `candidate` 或 `job`。

## 缺失字段和明确为空

完全不写 `skills` 表示“资料没有提供或没有成功抽取”，技能指标会保持 `unknown`。如果候选人已经确认资料完整，并明确表示没有已知技能，应同时填写：

```json
{
  "skills": [],
  "skills_confirmed_complete": true
}
```

此时空列表才会解释为明确事实，相应技能指标可以得到 `gap`。普通解析器产生的空数组不会自动当成“没有”。输出中的 `data_provenance.skills.status` 会记录 `provided`、`explicit_empty`、`omitted`、`extraction_failed` 或 `inferred`。

## 能力证据字段

候选人可以填写 `transferable_skills`、`toolchains`、`domain_knowledge`，以及责任担当、问题解决、沟通、利益相关方管理、交付、创新、风险、学习、适应、决策、分析、客户和合规等证据字段。对应字段名分别以 `_evidence` 结尾。

岗位一侧可以填写相应的要求或期望，如 `toolchains`、`domain_knowledge`、`ownership_expectations`、`problem_solving_expectations`、`communication_expectations` 和 `compliance_expectations`。完整字段可参考内置的 `assets/examples/candidate.json` 与 `assets/examples/job.json`。

## 技能的“且/或”关系

技能不是永远逐项都必须满足。岗位可以使用 `requirement_groups` 表达真实逻辑：

```json
{
  "requirement_groups": [
    {
      "id": "core-language",
      "operator": "all",
      "items": [{"name": "Python"}],
      "hard": true
    },
    {
      "id": "web-framework",
      "operator": "any",
      "minimum_match_count": 1,
      "items": [{"name": "FastAPI"}, {"name": "Django"}],
      "hard": false
    }
  ]
}
```

这表示 `Python AND (FastAPI OR Django)`。`operator: all` 要求全部满足；`operator: any` 配合 `minimum_match_count` 表示命中其中若干项。文本解析器也会识别“或、任选、任一、至少两项”等常见说法。`Python、FastAPI 或 Django` 会拆成 `Python AND (FastAPI OR Django)`；`Java、Go、Python 中至少一种` 保持为一个三选一逻辑组。在高影响场景中仍应让用户确认解析结果。

“必须、硬性、must、required”等标记默认只作用于当前逗号、分号或句号子句，不会扩散到同一行的其他条件。“以下条件均为必须”和“以下条件优先”会建立段落作用域，后续项目符号会继承，直到遇到“岗位职责、任职要求、薪资福利”等新章节标题。经验年限和学历是否为硬条件也使用相同作用域。

斜杠默认不直接解释成AND。`Java/Go任选一种` 是明确的OR；只写 `Java/Go` 时，解析结果采用保守OR，同时写入 `needs_confirmation: true` 和 `ambiguity_reason: slash_without_explicit_choice`。如果这个歧义组被标记为硬条件，硬门槛状态为 `unknown`，必须确认原意后才形成正式分。

## 薪资字段与文本格式

结构化薪资使用 `min`、`max`、`currency` 和 `period`。`period` 取 `month` 或 `year`，还可填写 `salary_months`、`salary_months_min`、`salary_months_max`、`variable_component` 和 `negotiable`。

文本解析支持 `8k-12k`、`1.5w-2w/月`、`8K—12K/月`、`8-12k·13薪`、`15k-20k·13-15薪`、`8000-12000元/月`、`月薪8000至12000元`、`年薪15-20万`、`15万-20万元/年`、`底薪8k+绩效` 和 `面议`。`13-15薪` 保存为 `salary_months_min: 13, salary_months_max: 15`。`8k以上`、`不低于8k` 和 `8k起` 保存为 `min: 8000, max: null`；`10k以内`、`10k以下` 保存为 `min: null, max: 10000`。解析器会排除教育日期、年月区间、年龄和经验年限；如果文本同时含教育日期和薪资，应优先使用带“薪资、月薪、年薪、待遇、底薪”等上下文的片段。

## 自然语言年限与办公方式

年限只在明确经验语境中提取，例如“3年工作经验”“拥有三年Python开发经验”“一年半数据分析经验”“两年左右开发经验”“三年以上研发经验”“三至五年项目经验”和“拥有2.5 years of experience”。范围写法按保守下限进入标量年限字段。`2025年9月`、`二〇二五年九月`、`2025届`、`出生于2005年` 和 `2022年毕业` 都按日期或届别处理，不进入 `experience_years`。

办公方式会识别否定语义。“不接受远程办公，期望现场办公”和“暂不支持远程办公，仅现场办公”都只保留 `onsite`；“不支持、不接受、不提供、暂不考虑、仅限现场”等表达不会因为出现“远程”二字就加入 `remote`。

`availability` 和 `availability_required` 使用 `YYYY-MM-DD`。引擎会按真实日历日期比较，无法解析时返回 `unknown`，不会退化为字符串大小比较。CLI、HTTP和逐行JSON都可提供 `as_of_date` 固定整次评分的基准日。

## 求职者偏好与岗位供给

| 求职者字段 | 岗位字段 | 含义 |
|---|---|---|
| `role_mission_preferences` | `role_mission` | 使命和方向 |
| `daily_task_interests` | `daily_tasks` | 日常任务兴趣 |
| `autonomy_preference` | `autonomy_level` | 自主权 |
| `feedback_frequency_preference` | `feedback_frequency` | 反馈频率 |
| `collaboration_style_preferences` | `collaboration_style` | 协作方式 |
| `decision_style_preferences` | `decision_style` | 决策方式 |
| `pace_preference` | `pace` | 工作节奏 |
| `learning_budget_expectation` | `learning_budget` | 学习预算 |
| `mentorship_preferences` | `mentorship` | 导师资源 |
| `promotion_clarity_preference` | `promotion_clarity` | 晋升透明度 |
| `bonus_expectation` | `bonus_range` | 奖金区间 |
| `min_annual_leave_days` | `annual_leave_days` | 年假天数 |
| `max_commute_minutes` | `commute_minutes` | 最长通勤 |
| `max_travel_days_per_month` | `travel_days_per_month` | 每月出差 |
| `psychological_safety_preferences` | `psychological_safety` | 工作氛围 |

此外还支持价值观、成长目标、行业兴趣、期望职级、工作量、办公方式、团队文化、岗位稳定性、福利、管理方式和职业路径等字段。

只有 `required_skills[].hard`、`experience_hard` 或 `education.hard` 明确为真时，条件才会被当作硬要求。硬要求为 `unknown` 时不形成正式分。年龄、性别、民族、婚育、宗教、健康、残障、政治面貌、户籍、照片和身份证号等信息即使出现在原始资料里，也只用于审计并从评分副本中排除。
