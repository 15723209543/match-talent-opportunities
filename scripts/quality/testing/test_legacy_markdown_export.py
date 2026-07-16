"""本文件验证旧版Markdown兼容导出不会泄露标签、生成链接结构或因异常字段崩溃。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))

from sample_data import candidate, job
from talentmatch.engine import match_pair
from talentmatch.reporting import to_markdown


class LegacyMarkdownExportTests(unittest.TestCase):
    """验证兼容入口复用统一清洗，同时保留原有报告结构。"""

    @classmethod
    def setUpClass(cls):
        cls.result = match_pair(candidate(), job())

    def test_legacy_summary_gates_and_metrics_are_escaped(self):
        probe = copy.deepcopy(self.result)
        probe["executive_summary"] = "<script>alert(1)</script>\n# 伪造标题"
        probe["gates"][0]["gate"] = "<img src=x>\n|伪造单元格|"
        probe["recruiter_dimensions"][0]["name"] = "![指标](javascript:alert(2))"
        markdown = to_markdown(probe)
        self.assertNotIn("<script", markdown)
        self.assertNotIn("<img", markdown)
        self.assertNotIn("\n# 伪造标题", markdown)
        self.assertNotIn("![指标](", markdown)
        self.assertIn("&lt;script&gt;", markdown)

    def test_legacy_evidence_recommendations_and_plan_are_escaped(self):
        probe = copy.deepcopy(self.result)
        probe["evidence_matrix"][0]["requirement"] = "<svg onload=alert(3)>"
        probe["evidence_matrix"][0]["evidence"] = "[点击](javascript:alert(4))\n|新列|"
        probe["recommendations"]["verified_gaps"] = [{"name": "<img src=x>"}]
        probe["recommendations"]["resume_actions"] = ["![探针](https://invalid.example/x)"]
        probe["recommendations"]["development_plan"] = {"<script>阶段</script>": ["<iframe src=x>"]}
        markdown = to_markdown(probe)
        for marker in ("<svg", "<img", "<script", "<iframe"):
            self.assertNotIn(marker, markdown)
        self.assertNotIn("[点击](javascript:", markdown)
        self.assertNotIn("![探针](", markdown)

    def test_legacy_prefixes_backslashes_and_newlines_are_neutralized(self):
        probe = copy.deepcopy(self.result)
        prefixes = ["=公式", "+公式", "-公式", "@公式", "\\反斜杠", "第一行\n第二行"]
        probe["recommendations"]["resume_actions"] = prefixes
        markdown = to_markdown(probe)
        self.assertIn("&#61;公式", markdown)
        self.assertIn("\\+公式", markdown)
        self.assertIn("\\-公式", markdown)
        self.assertIn("&#64;公式", markdown)
        self.assertIn("\\\\反斜杠", markdown)
        self.assertNotIn("第一行\n第二行", markdown)

    def test_legacy_invalid_numeric_and_collection_types_do_not_crash(self):
        probe = copy.deepcopy(self.result)
        probe["scores"]["overall"] = "<img src=x>"
        probe["confidence"]["score"] = "not-a-number<script>"
        probe["recruiter_dimensions"][0]["coefficient"] = {"bad": "<svg>"}
        probe["recommendations"]["resume_actions"] = "<iframe src=x>"
        probe["recommendations"]["development_plan"] = {"30天": "<script>alert(5)</script>"}
        markdown = to_markdown(probe)
        self.assertIn("## 8. 方法说明", markdown)
        for marker in ("<img", "<script", "<svg", "<iframe"):
            self.assertNotIn(marker, markdown)

    def test_export_markdown_cli_uses_the_safe_compatibility_renderer(self):
        probe = copy.deepcopy(self.result)
        probe["executive_summary"] = "<img src=x>\n![探针](javascript:alert(6))"
        script = SCRIPTS_DIR / "io_tools" / "export" / "export_markdown.py"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "result.json"
            output = Path(directory) / "report.md"
            source.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(source), "--output", str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            markdown = output.read_text(encoding="utf-8")
            self.assertNotIn("<img", markdown)
            self.assertNotIn("![探针](", markdown)
            self.assertIn("&lt;img", markdown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
