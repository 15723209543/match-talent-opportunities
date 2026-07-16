"""本文件覆盖最新复检提出的公平隔离、硬条件、隐私、接口、日期和展示边界。"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))

from sample_data import candidate, job
from talentmatch.analytics import _category_summary
from talentmatch.audit import audit_output
from talentmatch.batch import triage_candidates
from talentmatch.engine import match_pair
from talentmatch.evidence_loop import prepare_evidence_review, reassess_with_evidence
from talentmatch.metrics import MetricContext, evaluate_metric
from talentmatch.semantic_adapter import validate_semantic_extraction


def _load_http_module():
    """从独立脚本路径加载HTTP接口模块，直接验证请求契约。"""
    path = SCRIPTS_DIR / "interfaces" / "http" / "http_server.py"
    spec = importlib.util.spec_from_file_location("talentlens_http_server", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LatestReviewRegressionTests(unittest.TestCase):
    """确认最新复检中的阻塞问题不会再次出现。"""

    @classmethod
    def setUpClass(cls):
        cls.http = _load_http_module()

    def test_protected_candidate_phrase_does_not_change_score(self):
        base = candidate()
        protected = candidate()
        base["skills"][0]["evidence"] = "负责SQL优化工作并交付结果"
        protected["skills"][0]["evidence"] = "男性，30岁，已婚，户籍上海，负责SQL优化工作并交付结果"
        base_result = match_pair(base, job(), as_of_date="2026-07-15")
        protected_result = match_pair(protected, job(), as_of_date="2026-07-15")
        self.assertEqual(base_result["scores"]["provisional_overall"], protected_result["scores"]["provisional_overall"])
        self.assertTrue(protected_result["fairness_audit"]["candidate"]["scoring_sanitization_applied"])

    def test_discriminatory_job_phrase_does_not_change_score(self):
        base_job = job()
        protected_job = job()
        base_job["responsibilities"] = ["规划企业指标平台"]
        protected_job["responsibilities"] = ["限男性，年龄30岁以下，规划企业指标平台"]
        base_result = match_pair(candidate(), base_job, as_of_date="2026-07-15")
        protected_result = match_pair(candidate(), protected_job, as_of_date="2026-07-15")
        self.assertEqual(base_result["scores"]["provisional_overall"], protected_result["scores"]["provisional_overall"])
        self.assertTrue(protected_result["fairness_audit"]["job"]["protected_trait_flags"])

    def test_structured_protected_fields_are_removed_before_scoring(self):
        base = candidate()
        protected = {**candidate(), "age": 30, "gender": "male", "health_status": "healthy"}
        self.assertEqual(
            match_pair(base, job(), as_of_date="2026-07-15")["scores"]["provisional_overall"],
            match_pair(protected, job(), as_of_date="2026-07-15")["scores"]["provisional_overall"],
        )

    def test_unknown_hard_education_blocks_formal_score(self):
        candidate_data = candidate()
        candidate_data.pop("education", None)
        job_data = job()
        job_data["education"] = {"min_level": "bachelor", "hard": True}
        result = match_pair(candidate_data, job_data)
        self.assertEqual(result["scores"]["status"], "hard_requirement_unverified")
        self.assertIsNone(result["scores"]["overall"])

    def test_omitted_skills_are_unknown_not_gap(self):
        candidate_data = candidate()
        candidate_data.pop("skills", None)
        job_data = job()
        job_data["required_skills"] = [{"name": "SQL", "hard": True}]
        result = match_pair(candidate_data, job_data)
        metric = next(row for row in result["recruiter_dimensions"] if row["id"] == "required_skill_coverage")
        self.assertIsNone(metric["score"])
        self.assertEqual(metric["status"], "unknown")
        self.assertEqual(result["scores"]["status"], "hard_requirement_unverified")

    def test_confirmed_empty_skills_can_be_gap(self):
        candidate_data = candidate()
        candidate_data["skills"] = []
        candidate_data["skills_confirmed_complete"] = True
        job_data = job()
        job_data["required_skills"] = [{"name": "SQL", "hard": True}]
        result = match_pair(candidate_data, job_data)
        metric = next(row for row in result["recruiter_dimensions"] if row["id"] == "required_skill_coverage")
        self.assertEqual(metric["score"], 0.0)
        self.assertEqual(metric["status"], "gap")
        self.assertEqual(result["scores"]["status"], "hard_failure")

    def test_evidence_review_does_not_expose_pii(self):
        result = prepare_evidence_review(
            {"candidate_name": "张三", "phone": "13800138000", "email": "test@example.com"},
            job(),
        )
        payload = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("13800138000", payload)
        self.assertNotIn("test@example.com", payload)
        self.assertNotIn("张三", payload)

    def test_reassessment_update_is_redacted_and_summarized(self):
        result = reassess_with_evidence(
            candidate(),
            job(),
            {"candidate": {"phone": "13800138000", "email": "test@example.com"}},
        )
        payload = json.dumps(result["applied_update"], ensure_ascii=False)
        self.assertNotIn("13800138000", payload)
        self.assertNotIn("test@example.com", payload)
        self.assertIn("candidate.phone", result["applied_update"]["changed_fields"])

    def test_semantic_adapter_rejects_birth_date(self):
        with self.assertRaises(ValueError):
            validate_semantic_extraction({"candidate": {"birth_date": "1998-01-01"}, "job": {}})

    def test_semantic_adapter_rejects_height_and_household_registration(self):
        with self.assertRaises(ValueError):
            validate_semantic_extraction({"candidate": {"height": 175}, "job": {"household_registration": "上海"}})

    def test_http_rejects_top_level_array_with_stable_code(self):
        with self.assertRaises(self.http.RequestValidationError) as caught:
            self.http.validate_request_payload("/match", [])
        self.assertEqual(caught.exception.code, "invalid_json_object")

    def test_http_rejects_candidates_object_instead_of_array(self):
        with self.assertRaises(self.http.RequestValidationError) as caught:
            self.http.validate_request_payload("/rank-candidates", {"candidates": {"id": "C001"}})
        self.assertEqual(caught.exception.code, "candidates_must_be_array")

    def test_http_rejects_jobs_object_instead_of_array(self):
        with self.assertRaises(self.http.RequestValidationError) as caught:
            self.http.validate_request_payload("/rank-jobs", {"jobs": {"id": "J001"}})
        self.assertEqual(caught.exception.code, "jobs_must_be_array")

    def test_availability_uses_calendar_dates_not_strings(self):
        context = MetricContext(
            {"availability": "2026-8-2"},
            {"availability_required": "2026-10-01"},
            "2026-07-15",
        )
        self.assertEqual(evaluate_metric("start_date_alignment", context)["score"], 1.0)

    def test_invalid_availability_date_is_unknown(self):
        context = MetricContext({"availability": "2026-13-40"}, {"availability_required": "2026-10-01"})
        result = evaluate_metric("start_date_alignment", context)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "unknown")

    def test_salary_boundary_touch_is_eighty(self):
        context = MetricContext(
            {"salary_expectation": {"min": 20000, "max": 20000, "currency": "CNY", "period": "month"}},
            {"salary_range": {"min": 15000, "max": 20000, "currency": "CNY", "period": "month"}},
        )
        result = evaluate_metric("compensation_alignment", context)
        self.assertEqual(result["score"], 0.8)
        self.assertTrue(result["detail"]["boundary_touch"])

    def test_category_with_one_of_three_known_hides_display_score(self):
        rows = _category_summary([
            {"category": "资格条件", "effective_score": 100, "coefficient": 8, "status": "met"},
            {"category": "资格条件", "effective_score": None, "coefficient": 7, "status": "unknown"},
            {"category": "资格条件", "effective_score": None, "coefficient": 6, "status": "unknown"},
        ])
        self.assertEqual(rows[0]["score"], 100.0)
        self.assertIsNone(rows[0]["display_score"])
        self.assertEqual(rows[0]["status"], "insufficient_category_data")

    def test_scoring_context_records_fixed_as_of_date(self):
        result = match_pair(candidate(), job(), as_of_date="2026-07-15")
        self.assertEqual(result["scoring_context"]["as_of_date"], "2026-07-15")
        self.assertEqual(result["method"]["as_of_date"], "2026-07-15")

    def test_invalid_as_of_date_is_rejected(self):
        with self.assertRaises(ValueError):
            match_pair(candidate(), job(), as_of_date="2026-02-30")

    def test_unknown_priority_contains_field_paths(self):
        review = prepare_evidence_review({"id": "c"}, {"id": "j"})
        self.assertTrue(any(item["candidate_field_paths"] or item["job_field_paths"] for item in review["high_weight_unknowns"]))

    def test_unverified_hard_result_passes_output_audit(self):
        candidate_data = candidate()
        candidate_data.pop("education", None)
        job_data = job()
        job_data["education"] = {"min_level": "bachelor", "hard": True}
        result = match_pair(candidate_data, job_data, as_of_date="2026-07-15")
        audit = audit_output(result)
        self.assertTrue(audit["ok"])
        self.assertEqual(result["scores"]["status"], "hard_requirement_unverified")

    def test_batch_triage_separates_unverified_hard_requirements(self):
        candidate_data = candidate()
        candidate_data.pop("education", None)
        job_data = job()
        job_data["education"] = {"min_level": "bachelor", "hard": True}
        triage = triage_candidates([candidate_data], job_data, as_of_date="2026-07-15")
        self.assertEqual(triage["counts"]["unverified_hard_requirements"], 1)
        self.assertEqual(len(triage["unverified_hard_requirements"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
