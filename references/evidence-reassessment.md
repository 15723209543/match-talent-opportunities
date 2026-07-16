# 补充证据后怎样重新评估

一次匹配不应该是终点。真实招聘和求职过程中，很多关键事实会在沟通、面试和材料核验后才出现。TalentLens 把这个过程拆成可复核的八步：

1. 解析候选人和岗位资料；
2. 请当事人确认薪资、技能且/或关系、时间和证据；
3. 运行第一次双向匹配；
4. 找出高系数未知项；
5. 按指标类型生成候选人问题或企业确认问题；
6. 把经过确认的新事实写入补证JSON；
7. 重新匹配；
8. 对比状态、正式分、已知指标数和发生变化的指标。

## 先生成确认清单

```bash
python scripts/workflows/evidence/reassess_with_evidence.py \
  --candidate candidate.json \
  --job job.json \
  --output review.json
```

`review.json` 包含已经脱敏的保守解析结果、高权重未知项、应补充的候选人/岗位字段路径，以及面向候选人和企业的问题。此阶段标记为 `awaiting_confirmation`，不要擅自把问题答案补进资料。姓名、手机号、邮箱、地址和账号原值不会出现在导出结果中。

## 准备补证JSON

```json
{
  "candidate": {
    "skills": [
      {
        "name": "Python",
        "years": 3,
        "evidence": "负责订单服务接口，接口P95延迟下降31%，可提供压测记录"
      }
    ],
    "availability": "2026-08-10"
  },
  "job": {
    "work_modes": ["hybrid"],
    "salary_range": {
      "min": 18000,
      "max": 24000,
      "currency": "CNY",
      "period": "month"
    }
  }
}
```

只写已经确认的事实。补证内容会覆盖对应字段，因此数组字段应给出希望保留的完整值。

## 重新评估并查看变化

```bash
python scripts/workflows/evidence/reassess_with_evidence.py \
  --candidate candidate.json \
  --job job.json \
  --evidence-update evidence-update.json \
  --output reassessed.json
```

`comparison` 会列出补证前后状态、正式综合分、已知指标数和发生变化的指标。`applied_update` 只保留修改字段清单和脱敏预览，不回显完整敏感对象。第一次为 `insufficient_data` 或 `hard_requirement_unverified` 时，`before_public_score` 应为 `null`；系统不会拿诊断暂估值冒充正式提升。

补证重评不等于事实自动通过。证书、作品、指标口径和个人贡献仍需由有权限的人核验，并允许当事人更正。
