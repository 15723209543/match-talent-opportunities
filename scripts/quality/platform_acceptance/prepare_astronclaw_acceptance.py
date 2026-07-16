"""本脚本检查参赛ZIP的离线结构，并生成需要在AstronClaw真实环境人工完成的验收清单。"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="准备AstronClaw上传、安装与调用验收清单")
    parser.add_argument("--zip", required=True, help="待上传的Skill ZIP")
    parser.add_argument("--output", required=True, help="验收清单JSON")
    args = parser.parse_args()
    archive_path = Path(args.zip)
    with zipfile.ZipFile(archive_path) as archive:
        names = [name.replace("\\", "/") for name in archive.namelist() if not name.endswith("/")]
    required = ["SKILL.md", "README.md", "LICENSE.md", "reference_indicators/talent_matching_indicators.xlsx"]
    offline_checks = {
        "zip_readable": True,
        "skill_md_at_zip_root": "SKILL.md" in names,
        "required_files_present": all(name in names for name in required),
        "no_wrapper_directory": not any(name.startswith("match-talent-opportunities/") for name in names),
        "file_count": len(names),
    }
    payload = {
        "package": str(archive_path.resolve()),
        "offline_checks": offline_checks,
        "external_acceptance_status": "pending_real_platform_test",
        "external_steps": [
            {"step": "从比赛赛题页面上传ZIP，不绕过赛题页面", "completed": False, "evidence": ""},
            {"step": "等待SkillHub审核通过并记录版本号", "completed": False, "evidence": ""},
            {"step": "在AstronClaw新会话安装并读取SKILL.md", "completed": False, "evidence": ""},
            {"step": "调用HR单人匹配并核对JSON/HTML输出", "completed": False, "evidence": ""},
            {"step": "调用求职者双向匹配并核对暂不可比较逻辑", "completed": False, "evidence": ""},
            {"step": "调用面试官工作单与人才发展报告，确认版式不同", "completed": False, "evidence": ""},
            {"step": "修改Excel系数后重新调用，确认新请求使用新标准", "completed": False, "evidence": ""},
            {"step": "保存调用日志、截图、失败输入与平台版本", "completed": False, "evidence": ""},
        ],
        "notice": "离线检查不能替代AstronClaw真实上传、安装和调用测试；完成外部步骤前不得写成已适配验证。",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    boolean_checks = [
        offline_checks["zip_readable"],
        offline_checks["skill_md_at_zip_root"],
        offline_checks["required_files_present"],
        offline_checks["no_wrapper_directory"],
    ]
    ok = all(boolean_checks)
    print(json.dumps({"ok": ok, "output": str(output)}, ensure_ascii=False))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
