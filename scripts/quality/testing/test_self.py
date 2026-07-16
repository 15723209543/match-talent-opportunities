#!/usr/bin/env python3
"""本文件运行项目自测，覆盖80项指标、精度、硬条件、隐私、公平性和动态配置。"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from talentmatch.audit import audit_output
from talentmatch.engine import match_pair
from talentmatch.excel_config import DEFAULT_METRICS_WORKBOOK
from talentmatch.parser import parse_candidate, parse_job
from talentmatch.persona_reporting import write_persona_report
from talentmatch.privacy import redact


BASE_CANDIDATE = {
    "id": "c1",
    "target_roles": ["高级数据产品经理"],
    "skills": [
        {"name": "SQL", "level": 4, "years": 5, "evidence": "主导指标平台上线，查询效率提升40%"},
        {"name": "Python", "level": 3, "years": 3, "evidence": "使用Python自动化分析，每周节省8小时"},
        {"name": "需求分析", "level": 4, "years": 5, "evidence": "负责30+需求评审"},
    ],
    "experience_years": 5,
    "education": [{"level": "bachelor"}],
    "preferred_locations": ["上海"],
    "preferred_work_modes": ["hybrid"],
    "salary_expectation": {"min": 25000, "max": 32000, "currency": "CNY", "period": "month"},
    "employment_types": ["full-time"],
    "values": ["数据驱动"],
    "growth_goals": ["AI产品"],
}

BASE_JOB = {
    "id": "j1",
    "title": "高级数据产品经理",
    "responsibilities": ["建设企业指标平台", "推动跨团队需求交付"],
    "required_skills": [{"name": "SQL", "level": 3, "years": 3, "hard": True}, {"name": "需求分析"}],
    "preferred_skills": [{"name": "Python"}],
    "min_experience_years": 4,
    "education": {"min_level": "bachelor"},
    "location": "上海",
    "work_modes": ["hybrid"],
    "salary_range": {"min": 26000, "max": 35000, "currency": "CNY", "period": "month"},
    "employment_type": "full-time",
    "values": ["数据驱动"],
    "growth_offerings": ["AI产品"],
}


class TalentMatchTests(unittest.TestCase):
    def test_strong_pair_is_bounded_and_auditable(self):
        result = match_pair(BASE_CANDIDATE, BASE_JOB)
        self.assertEqual(result["scores"]["status"], "ready_for_review")
        self.assertGreaterEqual(result["scores"]["overall"], 65)
        self.assertLessEqual(result["scores"]["overall"], 100)
        self.assertTrue(audit_output(result)["ok"])
        self.assertEqual(result["scores"]["overall"], round(result["scores"]["overall"], 2))
        self.assertEqual(result["method"]["indicator_count"], 80)
        self.assertEqual(len(result["recruiter_dimensions"]) + len(result["candidate_dimensions"]), 80)
        self.assertIn("analytics", result)
        self.assertEqual(result["analytics"]["data_completeness"]["total_metrics"], 80)

    def test_explicit_hard_failure_caps_score(self):
        candidate = dict(BASE_CANDIDATE)
        candidate["skills"] = [{"name": "Excel", "evidence": "报表"}]
        result = match_pair(candidate, BASE_JOB)
        self.assertEqual(result["scores"]["status"], "hard_failure")
        self.assertIsNone(result["scores"]["overall"])
        self.assertLessEqual(result["scores"]["provisional_overall"], 49)
        self.assertTrue(any(gate["status"] == "fail" for gate in result["gates"]))

    def test_unknown_is_not_hard_failure(self):
        candidate = dict(BASE_CANDIDATE)
        candidate["skills"] = []
        result = match_pair(candidate, BASE_JOB)
        self.assertTrue(any(gate["status"] == "unknown" for gate in result["gates"]))
        self.assertFalse(any(gate["status"] == "fail" for gate in result["gates"]))

    def test_protected_criteria_are_flagged(self):
        result = match_pair(BASE_CANDIDATE, "数据产品经理\n要求SQL，限男性，年龄30岁以下")
        self.assertTrue(result["fairness_audit"]["job"]["protected_trait_flags"])
        self.assertFalse(result["method"]["protected_traits_used"])

    def test_pii_is_redacted(self):
        result = match_pair({**BASE_CANDIDATE, "skills": [{"name": "SQL", "evidence": "联系 13800138000, test@example.com"}]}, BASE_JOB)
        payload = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("13800138000", payload)
        self.assertNotIn("test@example.com", payload)
        self.assertNotIn("REDACTED_PHONE]T", result["meta"]["generated_at"])

    def test_raw_text_parsers_do_not_crash(self):
        candidate = parse_candidate("目标岗位：数据产品经理\n5年经验，熟悉SQL、Python")
        job = parse_job("高级数据产品经理\n任职要求：必须掌握SQL，3年以上经验；Python优先")
        self.assertTrue(candidate["skills"])
        self.assertTrue(job["required_skills"])

    def test_redactor(self):
        redacted, counts = redact("邮箱 test@example.com，手机13800138000")
        self.assertEqual(counts["email"], 1)
        self.assertGreaterEqual(counts["phone"], 1)
        self.assertIn("REDACTED", redacted)

    def test_excel_coefficient_is_reloaded_and_changes_score(self):
        candidate = dict(BASE_CANDIDATE)
        candidate["skills"] = [BASE_CANDIDATE["skills"][0]]
        baseline = match_pair(candidate, BASE_JOB)
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory) / "metrics.xlsx"
            with zipfile.ZipFile(DEFAULT_METRICS_WORKBOOK, "r") as source, zipfile.ZipFile(custom, "w", zipfile.ZIP_DEFLATED) as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == "xl/worksheets/sheet1.xml":
                        root = ET.fromstring(data)
                        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                        for cell in root.iter(namespace + "c"):
                            if cell.attrib.get("r") == "A2":
                                value_node = cell.find(namespace + "v")
                                self.assertIsNotNone(value_node)
                                value_node.text = "0.1"
                                break
                        data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    target.writestr(item, data)
            changed = match_pair(candidate, BASE_JOB, str(custom))
        self.assertNotEqual(baseline["method"]["indicator_workbook_sha256"], changed["method"]["indicator_workbook_sha256"])
        self.assertNotEqual(baseline["scores"]["provisional_overall"], changed["scores"]["provisional_overall"])

    def test_persona_reports_are_differentiated_and_visual(self):
        result = match_pair(BASE_CANDIDATE, BASE_JOB)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hr = write_persona_report(result, "hr", root / "hr.html", "html")
            candidate = write_persona_report(result, "candidate", root / "candidate.md", "markdown")
            self.assertEqual(len(hr["charts"]), 5)
            self.assertEqual(len(candidate["charts"]), 5)
            hr_text = (root / "hr.html").read_text(encoding="utf-8")
            candidate_text = (root / "candidate.md").read_text(encoding="utf-8")
            self.assertIn("HR候选人筛选与核验报告", hr_text)
            self.assertIn("求职者双向匹配与发展报告", candidate_text)
            self.assertNotEqual(hr_text, candidate_text)
            for chart in hr["charts"] + candidate["charts"]:
                self.assertTrue(Path(chart["path"]).read_text(encoding="utf-8").startswith("<svg"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
