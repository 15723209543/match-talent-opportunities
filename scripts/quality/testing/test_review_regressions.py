"""本文件回归测试复检提出的薪资、技能逻辑组、问题模板和角色报告问题。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.engine import match_pair
from talentmatch.gates import evaluate_gates
from talentmatch.parser import parse_candidate, parse_job
from talentmatch.persona_reporting import render_html, render_markdown
from talentmatch.recommendations import _question_for_dimension


class ReviewRegressionTests(unittest.TestCase):
    """覆盖用户复检中列出的高优先级边界条件。"""

    def test_salary_formats(self):
        samples = {
            "期望薪资：8k-12k/月": (8000, 12000, "month"),
            "薪资：5K—8K/月": (5000, 8000, "month"),
            "8-12k·13薪": (8000, 12000, "month"),
            "8000-12000元/月": (8000, 12000, "month"),
            "月薪8000至12000元": (8000, 12000, "month"),
            "年薪15-20万": (150000, 200000, "year"),
            "15万-20万元/年": (150000, 200000, "year"),
        }
        for text, expected in samples.items():
            with self.subTest(text=text):
                salary = parse_candidate(text)["salary_expectation"]
                self.assertEqual((salary["min"], salary["max"], salary["period"]), expected)

    def test_salary_single_base_and_negotiable(self):
        base = parse_job("底薪8k+绩效")["salary_range"]
        self.assertEqual(base["min"], 8000)
        self.assertTrue(base["variable_component"])
        self.assertTrue(parse_job("薪资面议")["salary_range"]["negotiable"])

    def test_salary_w_and_open_intervals(self):
        salary_range = parse_candidate("期望薪资：1.5w-2w/月")["salary_expectation"]
        self.assertEqual((salary_range["min"], salary_range["max"]), (15000, 20000))
        lower_samples = ("8k以上", "不低于8k", "8k起")
        upper_samples = ("10k以内", "10k以下")
        for text in lower_samples:
            with self.subTest(text=text):
                value = parse_candidate("期望薪资：" + text)["salary_expectation"]
                self.assertEqual((value["min"], value["max"]), (8000, None))
        for text in upper_samples:
            with self.subTest(text=text):
                value = parse_candidate("期望薪资：" + text)["salary_expectation"]
                self.assertEqual((value["min"], value["max"]), (None, 10000))

    def test_open_salary_interval_can_be_scored(self):
        result = match_pair(
            {"salary_expectation": {"min": 8000, "max": None, "currency": "CNY", "period": "month"}},
            {"salary_range": {"min": 10000, "max": 15000, "currency": "CNY", "period": "month"}},
        )
        metric = next(item for item in result["candidate_dimensions"] if item["id"] == "compensation_alignment")
        self.assertIsNotNone(metric["score"])
        self.assertTrue(metric["detail"]["open_interval"])

    def test_date_age_and_experience_are_not_salary(self):
        for text in ("本科 2025-2029", "年龄25-30岁", "要求3-5年经验"):
            with self.subTest(text=text):
                self.assertEqual(parse_candidate(text)["salary_expectation"], {})

    def test_salary_line_wins_over_education_date(self):
        salary = parse_candidate("本科 2025-2029\n期望薪资：8k-12k/月")["salary_expectation"]
        self.assertEqual((salary["min"], salary["max"]), (8000, 12000))

    def test_chinese_dates_do_not_become_experience(self):
        dated = parse_candidate("教育经历：2025年9月-2029年6月，本科\n项目经历：使用Python开发课程系统")
        graduated = parse_candidate("2022年7月毕业，拥有3年Python开发经验")
        self.assertIsNone(dated["experience_years"])
        self.assertEqual(graduated["experience_years"], 3.0)

    def test_experience_requires_explicit_context(self):
        self.assertEqual(parse_candidate("从事Python开发2.5年")["experience_years"], 2.5)
        self.assertEqual(parse_candidate("3 years of experience in Python")["experience_years"], 3.0)
        self.assertIsNone(parse_candidate("2025届，出生于2003年")["experience_years"])

    def test_chinese_number_experience_years(self):
        candidate_samples = {
            "拥有三年Python开发经验": 3.0,
            "具备一年半数据分析经验": 1.5,
            "从事Java开发两年左右": 2.0,
            "累计五年以上后端研发经验": 5.0,
        }
        for text, expected in candidate_samples.items():
            with self.subTest(text=text):
                self.assertEqual(parse_candidate(text)["experience_years"], expected)
        self.assertEqual(parse_job("要求三年以上Python开发经验")["min_experience_years"], 3.0)

    def test_chinese_experience_range_uses_conservative_lower_bound(self):
        self.assertEqual(parse_candidate("具有三至五年Python开发经验")["experience_years"], 3.0)
        self.assertEqual(parse_job("要求两到四年Java开发经验")["min_experience_years"], 2.0)

    def test_parser_builds_and_or_groups(self):
        job = parse_job("熟悉 Python，了解 FastAPI 或 Django")
        self.assertEqual([group["operator"] for group in job["requirement_groups"]], ["all", "any"])
        self.assertEqual(job["requirement_groups"][1]["minimum_match_count"], 1)

    def test_dunhao_keeps_prefix_as_and_before_or_group(self):
        job = parse_job("Python、FastAPI 或 Django")
        groups = job["requirement_groups"]
        self.assertEqual(len(groups), 2)
        self.assertEqual(([item["name"] for item in groups[0]["items"]], groups[0]["operator"]), (["python"], "all"))
        self.assertEqual((set(item["name"] for item in groups[1]["items"]), groups[1]["operator"]), ({"fastapi", "django"}, "any"))

    def test_go_alias_uses_context_and_word_boundaries(self):
        skills = {item["name"] for item in parse_job("Java、Go、Python 中至少一种")["required_skills"]}
        ordinary = {item["name"] for item in parse_candidate("I go to work by train")["skills"]}
        self.assertEqual(skills, {"java", "go", "python"})
        self.assertNotIn("go", ordinary)

    def test_at_least_two_skills_group(self):
        job = parse_job("Python、FastAPI、Django 中至少两种")
        group = job["requirement_groups"][0]
        self.assertEqual(group["operator"], "any")
        self.assertEqual(group["minimum_match_count"], 2)

    def test_any_group_counts_once_in_score(self):
        job = parse_job("熟悉 Python，了解 FastAPI 或 Django")
        result = match_pair({"skills": [{"name": "Python"}, {"name": "FastAPI"}]}, job)
        metric = next(row for row in result["recruiter_dimensions"] if row["id"] == "required_skill_coverage")
        self.assertEqual(metric["score"], 100.00)

    def test_hard_any_group_passes_with_one_exact_match(self):
        job = parse_job("必须掌握 FastAPI 或 Django")
        gates = evaluate_gates({"skills": [{"name": "FastAPI"}]}, job)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0]["status"], "pass")

    def test_hard_marker_does_not_spread_across_clauses(self):
        job = parse_job("任职要求：必须掌握 Java 或 Go，熟悉 MySQL")
        groups = job["requirement_groups"]
        mysql_group = next(group for group in groups if any(item["name"] == "mysql" for item in group["items"]))
        self.assertFalse(mysql_group["hard"])
        result = match_pair({"skills": [{"name": "Java"}]}, job)
        self.assertNotEqual(result["scores"]["status"], "hard_failure")

    def test_experience_hard_is_clause_scoped(self):
        soft = parse_job("必须掌握Java，要求3年工作经验")
        hard = parse_job("掌握Java，必须具备3年工作经验")
        global_hard = parse_job("以下条件均为必须：Java，3年工作经验")
        self.assertFalse(soft["experience_hard"])
        self.assertTrue(hard["experience_hard"])
        self.assertTrue(global_hard["experience_hard"])

    def test_multiline_hard_and_preferred_scopes_are_inherited(self):
        job = parse_job(
            "任职要求：\n"
            "以下条件均为必须：\n- Java\n- MySQL\n"
            "以下条件优先：\n- Redis\n- Docker"
        )
        hard_by_name = {item["name"]: item["hard"] for item in job["required_skills"]}
        preferred_names = {item["name"] for item in job["preferred_skills"]}
        self.assertTrue(hard_by_name["java"])
        self.assertTrue(hard_by_name["mysql"])
        self.assertEqual(preferred_names, {"redis", "docker"})
        self.assertTrue(all(not item["hard"] for item in job["preferred_skills"]))

    def test_multiline_scope_resets_at_new_section(self):
        job = parse_job("以下条件均为必须：\n- Java\n岗位职责：\n- 使用MySQL维护业务数据")
        mysql_group = next(group for group in job["requirement_groups"] if any(item["name"] == "mysql" for item in group["items"]))
        self.assertFalse(mysql_group["hard"])

    def test_slash_without_choice_is_marked_for_confirmation(self):
        job = parse_job("熟悉Java/Go")
        group = job["requirement_groups"][0]
        self.assertEqual({item["name"] for item in group["items"]}, {"java", "go"})
        self.assertEqual(group["operator"], "any")
        self.assertTrue(group["needs_confirmation"])
        self.assertEqual(group["ambiguity_reason"], "slash_without_explicit_choice")
        self.assertIn("ambiguous_slash_requirement_requires_confirmation", job["parser"]["warnings"])

    def test_slash_with_explicit_choice_is_or_without_ambiguity(self):
        job = parse_job("Java/Go任选一种")
        group = job["requirement_groups"][0]
        self.assertEqual({item["name"] for item in group["items"]}, {"java", "go"})
        self.assertEqual(group["operator"], "any")
        self.assertFalse(group["needs_confirmation"])

    def test_ambiguous_hard_slash_becomes_unknown_gate(self):
        job = parse_job("必须掌握Java/Go")
        gates = evaluate_gates({"skills": [{"name": "Java"}]}, job)
        self.assertEqual(gates[0]["status"], "unknown")
        self.assertEqual(gates[0]["reason"], "ambiguous_requirement_needs_confirmation")
        result = match_pair({"skills": [{"name": "Java"}]}, job)
        self.assertEqual(result["scores"]["status"], "hard_requirement_unverified")
        self.assertIsNone(result["scores"]["overall"])

    def test_salary_month_range_is_preserved(self):
        salary = parse_job("薪资：15k-20k·13-15薪")["salary_range"]
        self.assertEqual((salary["min"], salary["max"]), (15000, 20000))
        self.assertEqual((salary["salary_months_min"], salary["salary_months_max"]), (13, 15))

    def test_negated_work_modes_are_excluded(self):
        candidate = parse_candidate("不接受远程办公，期望现场办公")
        job = parse_job("本岗位暂不支持远程办公，仅现场办公")
        self.assertEqual(candidate["preferred_work_modes"], ["onsite"])
        self.assertEqual(job["work_modes"], ["onsite"])

    def test_public_report_hides_provisional_score(self):
        result = match_pair({"id": "c"}, {"id": "j"})
        html = render_html(result, "candidate", [])
        markdown = render_markdown(result, "candidate")
        self.assertIn("暂不可比较", html)
        self.assertIn("暂不可比较", markdown)
        self.assertNotIn("<small>暂估</small>", html)

    def test_salary_question_is_not_star(self):
        question = _question_for_dimension({"id": "compensation_alignment", "name": "薪酬匹配"}, "candidate")
        self.assertIn("薪资范围", question["question"])
        self.assertNotIn("STAR", question["question"])

    def test_location_and_availability_questions_are_specific(self):
        location = _question_for_dimension({"id": "commute_feasibility", "name": "通勤"}, "candidate")
        availability = _question_for_dimension({"id": "start_date_alignment", "name": "到岗"}, "candidate")
        self.assertIn("通勤", location["question"])
        self.assertIn("通知期", availability["question"])

    def test_experience_question_uses_timeline_not_star(self):
        question = _question_for_dimension({"id": "total_experience", "name": "总经验年限"}, "candidate")
        self.assertIn("开始和结束年月", question["question"])
        self.assertIn("重叠时间", question["question"])
        self.assertNotIn("STAR", question["question"])

    def test_candidate_report_always_has_basic_employer_questions(self):
        result = match_pair({"id": "c"}, {"id": "j"})
        questions = result["recommendations"]["job_confirmation_questions"]
        ids = {item["indicator_id"] for item in questions}
        self.assertIn("compensation_alignment", ids)
        self.assertIn("work_mode_preference_alignment", ids)
        self.assertIn("manager_style_alignment", ids)

    def test_four_html_reports_have_distinct_operating_sections(self):
        result = match_pair({"id": "c"}, {"id": "j"})
        expected = {
            "hr": "候选人分流与人工复核",
            "candidate": "向企业确认的问题",
            "interviewer": "面试记录区",
            "talent_manager": "能力矩阵",
        }
        for persona, heading in expected.items():
            with self.subTest(persona=persona):
                self.assertIn(heading, render_html(result, persona, []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
