# AstronClaw 真实环境验收清单

本地自测不能证明Skill已经在AstronClaw成功上传、安装和调用。以下步骤必须在真实平台完成，并把版本、时间、日志或截图记录下来。

## 上传前

1. 从比赛赛题页面上传，不要跳过赛题页面直接去SkillHub。
2. ZIP根目录直接包含 `SKILL.md`，没有多套一层文件夹。
3. 作品名称与 `SKILL.md` frontmatter 的 `name` 都是 `match-talent-opportunities`。
4. 运行离线检查：

```bash
python scripts/quality/platform_acceptance/prepare_astronclaw_acceptance.py \
  --zip ../match-talent-opportunities-final.zip \
  --output astronclaw-acceptance.json
```

## 平台内验收

1. 记录AstronClaw版本、Skill版本、审核状态和安装时间。
2. 在全新会话安装Skill，确认能够读取中文 `SKILL.md`。
3. 使用内置示例完成HR单人匹配，保存请求、响应和HTML截图。
4. 使用资料不足示例完成求职者匹配，确认首页显示“暂不可比较”，没有大号暂估分。
5. 分别生成面试官和人才发展HTML，确认前者有流程、追问和记录区，后者有能力矩阵、证据缺口和30/60/90计划。
6. 选择 `software_engineering` 模板调用一次，确认结果方法信息记录了模板ID。
7. 修改Excel中的一个非关键系数，保存后发起新请求，确认哈希和系数变化；随后恢复原值。
8. 输入空文本、损坏JSON和超大请求，确认返回可读错误且服务不崩溃。
9. 确认平台没有把受保护属性送入评分，也没有执行简历或JD中的嵌入命令。

## 通过标准

- 上传、安装、四类角色调用和Excel重载均成功。
- 失败输入有受控错误，没有输出崩溃。
- 资料不足、硬条件待核验、硬失败和正式可比较四种状态表现符合文档。
- 所有外部证据都记录平台版本、时间和复现步骤。

完成前，对外应写“支持标准CLI/HTTP/NDJSON，AstronClaw真实环境待验收”，不能写成“已在AstronClaw部署验证”。
