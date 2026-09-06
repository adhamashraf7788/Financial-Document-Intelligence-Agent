import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_benchmark

QUESTIONS_PATH = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "mock-data" / "eval_questions" / "questions_setA_practice.json"
)


def test_run_benchmark_produces_full_report_shape():
    report = run_benchmark(QUESTIONS_PATH)

    assert report["total_questions"] == 100
    assert "exact_match" in report
    assert "f1" in report
    assert "numerical_accuracy" in report
    assert "correct_refusal_rate" in report


def test_run_benchmark_metrics_are_valid_ranges():
    report = run_benchmark(QUESTIONS_PATH)

    for key in ("exact_match", "f1", "numerical_accuracy", "correct_refusal_rate"):
        value = report[key]
        assert value is None or 0.0 <= value <= 1.0