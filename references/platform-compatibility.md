# 可以在哪些平台使用

TalentLens 的核心运行条件是 Python 3.10 或更高版本。不同平台不需要共用同一种插件协议，只要从下面三种入口里选择一种即可。

| 使用环境 | 推荐入口 |
|---|---|
| Windows、macOS、Linux终端或CI | `scripts/interfaces/cli/talentlens.py` |
| AstronClaw / Astron SkillHub | `SKILL.md` + 统一CLI或角色脚本；需在真实平台完成验收 |
| Claude Code、Codex、Gemini CLI等本地助手 | 读取 `SKILL.md` 后调用CLI |
| Dify、Coze、n8n、Flowise、自建后端 | `scripts/interfaces/http/http_server.py` |
| LangChain、LlamaIndex、桌面应用、编辑器插件 | HTTP或 `scripts/interfaces/stdio/json_stdio.py` |
| 批处理和审计任务 | CLI + JSON结果 + Excel哈希 |

## 命令行接口

```bash
python scripts/interfaces/cli/talentlens.py match --candidate candidate.json --job job.json --profile general --persona candidate --format json
```

适合能运行本地命令并读取标准输出的平台。退出码、错误信息和JSON结构保持稳定，便于脚本和持续集成使用。

## 逐行JSON接口

先启动：

```bash
python scripts/interfaces/stdio/json_stdio.py --metrics reference_indicators/talent_matching_indicators.xlsx
```

随后每行写入一个请求，每行读取一个响应，单行上限2MB：

```json
{"request_id":"r1","operation":"health"}
{"request_id":"r2","operation":"match","audience":"candidate","profile":"product_operations","as_of_date":"2026-07-15","candidate":{"id":"c1","target_roles":["数据产品经理"]},"job":{"id":"j1","title":"数据产品经理"}}
```

支持 `health`、`match`、`rank_candidates` 和 `rank_jobs`。单个请求出错时返回 `ok:false`，长期子进程仍可继续处理下一行。请求中不能传 `metrics` 路径；如需更换Excel，必须在启动进程时使用 `--metrics`。

## HTTP接口

```bash
python scripts/interfaces/http/http_server.py --host 127.0.0.1 --port 8765 --metrics reference_indicators/talent_matching_indicators.xlsx
```

可用端点是 `GET /health`、`POST /match`、`POST /rank-candidates` 和 `POST /rank-jobs`。一个匹配请求可以写成：

```json
{
  "request_id": "r3",
  "audience": "hr",
  "profile": "product_operations",
  "as_of_date": "2026-07-15",
  "persona_view": true,
  "candidate": {"id": "c1", "target_roles": ["数据产品经理"], "skills": ["SQL"]},
  "job": {"id": "j1", "title": "数据产品经理", "required_skills": ["SQL"]}
}
```

服务默认只监听 `127.0.0.1`。确实需要绑定其他地址时必须显式添加 `--allow-remote`，并在外层配置HTTPS、身份认证、授权、限流、日志脱敏和审计。

单个HTTP请求不能指定指标文件。批量候选人或岗位最多100项，多对多矩阵最多2500对。排序响应按 `ready_for_review`、`needs_more_data`、`unverified_hard_requirements`、`hard_failures` 分流，后三组没有正式名次。请求体顶层必须是JSON对象，`candidates` 和 `jobs` 必须是对象数组；结构错误返回400和稳定错误码，不会转成500。

## 给智能助手的接入说明

能执行本地命令的助手应先阅读 `SKILL.md`，根据用户身份选择 `--persona` 或角色脚本，再读取结构化结果进行解释。工作流平台应优先使用HTTP；需要长期、低开销子进程的桌面工具可选逐行JSON。

平台不能运行本地Python时，可以把HTTP层部署到经过授权的受控服务。含个人信息的简历不应直接传给未经授权的第三方服务。

## 可选语义抽取层

任何能输出JSON的模型或平台都可以先把自然语言简历和JD抽取成结构化字段，再调用本地引擎。模型只负责解析、同义词归一、技能且/或关系和证据片段；它不直接给匹配分。

```bash
python scripts/interfaces/semantic/validate_extraction.py --print-contract
python scripts/interfaces/semantic/validate_extraction.py --input extraction.json --output normalized.json
```

校验器会拒绝无法在原文中定位的证据片段和进入评分结构的受保护属性。校验后的候选人与岗位对象再交给CLI、HTTP或NDJSON评分，因此核心功能不依赖某一个模型、网络或供应商。

## AstronClaw验收状态

本地测试只能确认ZIP结构、脚本、接口和输出，不能替代AstronClaw的真实上传、安装和调用。打包后运行：

```bash
python scripts/quality/platform_acceptance/prepare_astronclaw_acceptance.py --zip ../match-talent-opportunities.zip --output astronclaw-acceptance.json
```

随后按 `astronclaw-acceptance.json` 和 `astronclaw-acceptance.md` 在真实平台逐项填写版本、日志和截图。完成前应把状态写成“待真实平台验收”，不能宣称已经部署验证。
