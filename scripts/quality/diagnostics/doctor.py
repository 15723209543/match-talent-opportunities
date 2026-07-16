#!/usr/bin/env python3
"""本文件检查Python版本、目录结构、指标文件和示例运行是否处于可用状态。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import json
import platform
import sys
from pathlib import Path

from talentmatch.excel_config import load_metric_config, validate_metric_config
from talentmatch.metrics import METRIC_FUNCTIONS
from talentmatch.ontology import load_ontology


def main() -> int:
    root = _scripts_dir.parent
    required = [
        root / "SKILL.md",
        root / "reference_indicators" / "talent_matching_indicators.xlsx",
        root / "references" / "skill-ontology.json",
        root / "assets" / "examples" / "candidate.json",
        root / "assets" / "examples" / "job.json",
    ]
    persona_folders = ["hr", "candidate", "interviewer", "talent_manager"]
    errors = validate_metric_config()
    config = load_metric_config() if not errors else {"metric_count": 0, "metrics": [], "sha256": ""}
    configured_ids = {item["id"] for item in config.get("metrics", [])}
    available_profiles = [item.get("id", "") for item in config.get("available_profiles", [])]
    checks = {
        "python": platform.python_version(),
        "python_supported": sys.version_info >= (3, 10),
        "required_files": {str(path.relative_to(root)): path.exists() for path in required},
        "metric_workbook_valid": not errors,
        "metric_workbook_errors": errors,
        "configured_metric_count": config.get("metric_count", 0),
        "implemented_metric_count": len(METRIC_FUNCTIONS),
        "unimplemented_metric_ids": sorted(configured_ids - set(METRIC_FUNCTIONS)),
        "metric_workbook_sha256": config.get("sha256", ""),
        "available_weight_profiles": available_profiles,
        "required_weight_profiles_present": all(
            profile in available_profiles
            for profile in ["general", "software_engineering", "product_operations", "sales_customer"]
        ),
        "persona_script_counts": {
            folder: len(list((root / "scripts" / folder).rglob("*.py")))
            for folder in persona_folders
        },
        "ontology_skill_count": len(load_ontology().get("skills", {})),
        "loose_python_files_in_scripts_root": len(list((root / "scripts").glob("*.py"))),
        "network_required": False,
    }
    checks["ok"] = (
        checks["python_supported"]
        and all(checks["required_files"].values())
        and checks["metric_workbook_valid"]
        and checks["configured_metric_count"] == 80
        and checks["implemented_metric_count"] == 80
        and not checks["unimplemented_metric_ids"]
        and checks["required_weight_profiles_present"]
        and all(count >= 5 for count in checks["persona_script_counts"].values())
        and checks["loose_python_files_in_scripts_root"] == 0
        and checks["ontology_skill_count"] >= 50
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ok"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
