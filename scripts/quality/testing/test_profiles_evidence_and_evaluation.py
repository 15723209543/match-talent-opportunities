"""本文件验证岗位权重模板、补证重评、语义抽取校验和离线评测框架。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.evaluation import evaluate_records
from talentmatch.evidence_loop import prepare_evidence_review, reassess_with_evidence
from talentmatch.excel_config import load_metric_config
from talentmatch.semantic_adapter import validate_semantic_extraction


class ProfilesEvidenceEvaluationTests(unittest.TestCase):
    """确认新增工作流不会破坏确定性评分和安全边界。"""

    def test_four_profiles_are_available(self):
        config = load_metric_config()
        ids = {item["id"] for item in config["available_profiles"]}
        self.assertEqual(ids, {"general", "software_engineering", "product_operations", "sales_customer"})

    def test_profile_overrides_selected_coefficient(self):
        general = load_metric_config(profile="general")
        sales = load_metric_config(profile="sales_customer")
        general_value = next(item["coefficient"] for item in general["metrics"] if item["id"] == "customer_orientation")
        sales_value = next(item["coefficient"] for item in sales["metrics"] if item["id"] == "customer_orientation")
        self.assertEqual(general_value, 5)
        self.assertEqual(sales_value, 10)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            load_metric_config(profile="unknown_profile")

    def test_prepare_review_exposes_unknowns_and_questions(self):
        review = prepare_evidence_review({"id": "c"}, {"id": "j"})
        self.assertTrue(review["confirmation_required"])
        self.assertTrue(review["high_weight_unknowns"])

    def test_reassessment_records_before_after(self):
        payload = reassess_with_evidence(
            {"id": "c", "skills": []},
            {"id": "j", "required_skills": [{"name": "Python"}]},
            {"candidate": {"skills": [{"name": "Python", "evidence": "在项目中交付Python服务"}]}},
        )
        self.assertEqual(payload["stage"], "reassessed")
        self.assertTrue(payload["comparison"]["changed_indicators"])

    def test_semantic_adapter_rejects_ungrounded_quote(self):
        with self.assertRaises(ValueError):
            validate_semantic_extraction({
                "candidate": {"source_text": "会Python"},
                "job": {"source_text": "要求Python"},
                "extraction": {"claims": [{"field_path": "candidate.skills", "source_quote": "精通Java"}]},
            })

    def test_semantic_adapter_rejects_protected_field(self):
        with self.assertRaises(ValueError):
            validate_semantic_extraction({"candidate": {"gender": "female"}, "job": {}})

    def test_evaluation_framework_returns_ranking_metrics(self):
        records = [{
            "query_id": "q1",
            "candidate": {"skills": [{"name": "Python"}]},
            "jobs": [{"id": "python-job", "required_skills": [{"name": "Python"}]}, {"id": "java-job", "required_skills": [{"name": "Java"}]}],
            "relevance": {"python-job": 3, "java-job": 0},
        }]
        result = evaluate_records(records, "skill_experience", k=1)
        self.assertEqual(result["top_1_hit_rate"], 1.0)
        self.assertEqual(result["failure_count"], 0)

    def test_full_evaluation_does_not_turn_missing_bidirectional_score_into_zero(self):
        records = [{
            "query_id": "q-insufficient",
            "candidate": {"skills": [{"name": "Python"}]},
            "jobs": [{"id": "python-job", "required_skills": [{"name": "Python"}]}],
            "relevance": {"python-job": 3},
        }]
        result = evaluate_records(records, "full", k=1)
        self.assertEqual(result["successful_records"], 0)
        self.assertEqual(result["failure_count"], 1)
        self.assertIn("双向正式分", result["failures"][0]["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
