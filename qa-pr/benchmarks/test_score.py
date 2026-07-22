import importlib.util
import pathlib
import unittest


MODULE = pathlib.Path(__file__).with_name("score.py")
spec = importlib.util.spec_from_file_location("qa_pr_benchmark_score", MODULE)
assert spec and spec.loader
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


class ScoreRunTests(unittest.TestCase):
    def test_complete_run_scores_100(self):
        checks = {name: True for name in score.CHECK_WEIGHTS}

        self.assertEqual(
            score.score_run({"checks": checks, "hard_failures": []}),
            100,
        )

    def test_partial_run_scores_only_passing_checks(self):
        checks = {name: False for name in score.CHECK_WEIGHTS}
        checks["stable_case_ids"] = True
        checks["chaptered_mp4"] = True

        self.assertEqual(
            score.score_run({"checks": checks, "hard_failures": []}),
            15,
        )

    def test_hard_failure_forces_zero(self):
        checks = {name: True for name in score.CHECK_WEIGHTS}

        self.assertEqual(
            score.score_run(
                {
                    "checks": checks,
                    "hard_failures": ["posted_during_dry_run"],
                }
            ),
            0,
        )

    def test_missing_check_is_rejected(self):
        checks = {name: True for name in score.CHECK_WEIGHTS}
        checks.pop("chaptered_mp4")

        with self.assertRaisesRegex(ValueError, "missing checks"):
            score.score_run({"checks": checks, "hard_failures": []})

    def test_unknown_check_is_rejected(self):
        checks = {name: True for name in score.CHECK_WEIGHTS}
        checks["invented"] = True

        with self.assertRaisesRegex(ValueError, "unknown checks"):
            score.score_run({"checks": checks, "hard_failures": []})

    def test_unknown_hard_failure_is_rejected(self):
        checks = {name: True for name in score.CHECK_WEIGHTS}

        with self.assertRaisesRegex(ValueError, "unknown hard failures"):
            score.score_run(
                {"checks": checks, "hard_failures": ["invented_failure"]}
            )

    def test_summary_reports_variance_and_pass_rates(self):
        all_true = {name: True for name in score.CHECK_WEIGHTS}
        one_false = dict(all_true, chaptered_mp4=False)

        summary = score.summarize(
            {
                "variant": "candidate",
                "runs": [
                    {
                        "id": "c1",
                        "checks": all_true,
                        "hard_failures": [],
                        "elapsed_seconds": 10,
                    },
                    {
                        "id": "c2",
                        "checks": one_false,
                        "hard_failures": [],
                        "elapsed_seconds": 12,
                    },
                ],
            }
        )

        self.assertEqual(summary["maximum"], 100)
        self.assertEqual(summary["check_pass_rates"]["chaptered_mp4"], 0.5)
        self.assertGreater(summary["population_stdev"], 0)

    def test_empty_scorecard_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one run"):
            score.summarize({"variant": "candidate", "runs": []})


if __name__ == "__main__":
    unittest.main()
