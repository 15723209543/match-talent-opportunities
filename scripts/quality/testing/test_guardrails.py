"""本文件回归测试资料不足、布尔值、硬条件、精度和证据追溯等评分防线。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))

from sample_data import candidate, job
from talentmatch.audit import audit_output
from talentmatch.engine import match_pair
from talentmatch.model import parse_bool
from talentmatch.parser import parse_job


class GuardrailTests(unittest.TestCase):
    """验证评分结果不会在信息不足或硬条件异常时误导使用者。"""

    def test_empty_job_has_no_formal_score(self):
        result = match_pair({"id": "c", "skills": []}, {"id": "j"})
        self.assertEqual(result["scores"]["status"], "insufficient_data")
        self.assertIsNone(result["scores"]["overall"])

    def test_empty_job_confidence_is_below_threshold(self):
        result = match_pair({"id": "c", "skills": []}, {"id": "j"})
        self.assertLess(result["confidence"]["score"], 60)

    def test_strong_pair_is_ready_for_review(self):
        result = match_pair(candidate(), job())
        self.assertEqual(result["scores"]["status"], "ready_for_review")
        self.assertIsNotNone(result["scores"]["overall"])

    def test_hard_failure_removes_formal_score(self):
        result = match_pair(candidate(experience_years=2), job(min_experience_years=8, experience_hard=True))
        self.assertEqual(result["scores"]["status"], "hard_failure")
        self.assertIsNone(result["scores"]["overall"])

    def test_hard_failure_provisional_score_is_capped(self):
        result = match_pair(candidate(), job(min_experience_years=8, experience_hard=True))
        self.assertLessEqual(result["scores"]["provisional_overall"], 49)

    def test_string_false_is_false(self):
        parsed = parse_job(job(experience_hard="false"))
        self.assertFalse(parsed["experience_hard"])

    def test_string_zero_is_false(self):
        parsed = parse_job(job(experience_hard="0"))
        self.assertFalse(parsed["experience_hard"])

    def test_skill_hard_string_false_is_false(self):
        parsed = parse_job(job(required_skills=[{"name": "SQL", "hard": "false"}]))
        self.assertFalse(parsed["required_skills"][0]["hard"])

    def test_ambiguous_boolean_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_bool("sometimes", "hard")

    def test_no_required_skills_is_not_applicable(self):
        result = match_pair(candidate(), job(required_skills=[]))
        row = next(item for item in result["recruiter_dimensions"] if item["id"] == "required_skill_coverage")
        self.assertEqual(row["status"], "not_applicable")
        self.assertIsNone(row["score"])

    def test_metric_has_traceable_evidence(self):
        result = match_pair(candidate(), job())
        row = next(item for item in result["recruiter_dimensions"] if item["id"] == "required_skill_coverage")
        self.assertTrue(row["evidence_refs"])
        self.assertIn(row["evidence_refs"][0]["evidence_grade"], {"A", "B", "C"})

    def test_scores_keep_two_decimal_contract(self):
        result = match_pair(candidate(), job())
        for key in ("overall", "recruiter", "candidate"):
            self.assertEqual(result["scores"][key], round(result["scores"][key], 2))

    def test_output_audit_accepts_ready_result(self):
        self.assertTrue(audit_output(match_pair(candidate(), job()))["ok"])

    def test_output_audit_accepts_insufficient_result(self):
        self.assertTrue(audit_output(match_pair({"id": "c"}, {"id": "j"}))["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
