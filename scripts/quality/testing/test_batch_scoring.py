"""本文件验证批量分流、正式排序资格、规模限制和单请求Excel读取策略。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TEST_DIR))

from sample_data import candidate, job
from talentmatch import batch
from talentmatch.batch import match_matrix, rank_candidates, rank_jobs, triage_candidates, triage_jobs
from talentmatch.excel_config import load_metric_config


def non_hard_job(**updates):
    """返回不会把资料缺失直接判为硬性不符的岗位。"""
    base = job(required_skills=[{"name": "SQL", "hard": False}, {"name": "需求分析", "hard": False}])
    base.update(updates)
    return base


class BatchScoringTests(unittest.TestCase):
    """确保只有可比较结果进入排名，其余结果保留在人工处理队列。"""

    def test_candidates_are_split_into_ready_and_needs_data(self):
        result = triage_candidates([candidate(id="ready"), {"id": "missing"}], non_hard_job())
        self.assertEqual(result["counts"]["ready_for_review"], 1)
        self.assertEqual(result["counts"]["needs_more_data"], 1)

    def test_hard_failure_has_separate_bucket(self):
        result = triage_candidates([candidate(id="ready"), candidate(id="hard", experience_years=0)], job(experience_hard=True))
        self.assertEqual(result["counts"]["hard_failures"], 1)

    def test_needs_data_has_no_rank(self):
        result = triage_candidates([{"id": "missing"}], non_hard_job())
        self.assertIsNone(result["needs_more_data"][0]["rank"])

    def test_ready_results_receive_consecutive_ranks(self):
        result = triage_candidates([candidate(id="b"), candidate(id="a")], non_hard_job())
        self.assertEqual([row["rank"] for row in result["ready_for_review"]], [1, 2])

    def test_compatibility_rank_candidates_returns_ready_only(self):
        rows = rank_candidates([candidate(id="ready"), {"id": "missing"}], non_hard_job())
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["rank_eligible"])

    def test_jobs_are_split_into_ready_and_needs_data(self):
        result = triage_jobs(candidate(), [non_hard_job(id="ready"), {"id": "empty"}])
        self.assertEqual(result["counts"]["ready_for_review"], 1)
        self.assertEqual(result["counts"]["needs_more_data"], 1)

    def test_compatibility_rank_jobs_returns_ready_only(self):
        rows = rank_jobs(candidate(), [non_hard_job(id="ready"), {"id": "empty"}])
        self.assertEqual(len(rows), 1)

    def test_batch_candidate_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            triage_candidates([{"id": str(index)} for index in range(101)], non_hard_job())

    def test_batch_job_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            triage_jobs(candidate(), [{"id": str(index)} for index in range(101)])

    def test_matrix_pair_limit_is_enforced_before_matching(self):
        with self.assertRaises(ValueError):
            match_matrix([{"id": f"c{index}"} for index in range(51)], [{"id": f"j{index}"} for index in range(50)])

    def test_matrix_rows_include_comparability_status(self):
        result = match_matrix([candidate()], [non_hard_job()])
        self.assertEqual(result["matches"][0]["status"], "ready_for_review")

    def test_batch_loads_excel_once(self):
        with patch.object(batch, "load_metric_config", wraps=load_metric_config) as mocked:
            triage_candidates([candidate(id="a"), candidate(id="b")], non_hard_job())
            self.assertEqual(mocked.call_count, 1)

    def test_metric_workbook_has_eighty_metrics(self):
        self.assertEqual(load_metric_config()["metric_count"], 80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
