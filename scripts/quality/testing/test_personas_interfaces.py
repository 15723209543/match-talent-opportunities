"""本文件验证四类用户报告差异、角色校验以及逐行JSON接口的稳定行为。"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))

from sample_data import candidate, job
from talentmatch.engine import match_pair
from talentmatch.persona_reporting import build_persona_payload, render_html, render_markdown, write_persona_report


def _load_stdio_module():
    """从独立脚本路径加载逐行JSON接口模块。"""
    path = SCRIPTS_DIR / "interfaces" / "stdio" / "json_stdio.py"
    spec = importlib.util.spec_from_file_location("talentlens_json_stdio", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PersonaInterfaceTests(unittest.TestCase):
    """验证不同角色看到不同结构，错误角色不会静默退回HR。"""

    @classmethod
    def setUpClass(cls):
        cls.result = match_pair(candidate(), job())
        cls.stdio = _load_stdio_module()

    def test_hr_payload_has_review_fields(self):
        payload = build_persona_payload(self.result, "hr")
        self.assertIn("manual_review_queue_reasons", payload)
        self.assertIn("fairness_notice", payload)

    def test_candidate_payload_has_personal_actions(self):
        payload = build_persona_payload(self.result, "candidate")
        self.assertIn("job_conditions_to_confirm", payload)
        self.assertIn("do_not_overclaim", payload)

    def test_interviewer_payload_has_scorecard(self):
        payload = build_persona_payload(self.result, "interviewer")
        self.assertIn("scorecard_dimensions", payload)
        self.assertIn("prohibited_topics", payload)

    def test_talent_manager_payload_has_development_fields(self):
        payload = build_persona_payload(self.result, "talent_manager")
        self.assertIn("development_priorities", payload)
        self.assertIn("success_evidence", payload)

    def test_invalid_persona_is_rejected(self):
        with self.assertRaises(ValueError):
            build_persona_payload(self.result, "unknown_role")

    def test_hr_markdown_has_hr_title(self):
        self.assertIn("HR候选人筛选与核验报告", render_markdown(self.result, "hr"))

    def test_candidate_markdown_has_candidate_title(self):
        self.assertIn("求职者双向匹配与发展报告", render_markdown(self.result, "candidate"))

    def test_interviewer_markdown_has_interviewer_title(self):
        self.assertIn("面试官结构化核验工作单", render_markdown(self.result, "interviewer"))

    def test_talent_manager_html_has_role_title(self):
        self.assertIn("人才发展与内部流动建议报告", render_html(self.result, "talent_manager", []))

    def test_json_report_contains_persona_view(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_persona_report(self.result, "interviewer", path, "json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["persona"]["audience"], "interviewer")

    def test_stdio_returns_requested_persona(self):
        payload = self.stdio.handle({"operation": "match", "candidate": candidate(), "job": job(), "audience": "candidate"})
        self.assertEqual(payload["audience"], "candidate")

    def test_stdio_rejects_request_metrics_path(self):
        with self.assertRaises(ValueError):
            self.stdio.handle({"operation": "health", "metrics": "C:/outside.xlsx"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
