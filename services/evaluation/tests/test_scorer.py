import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scorer import exact_match, f1_score, numerical_accuracy, retrieval_recall_at_k, retrieval_precision_at_k, reciprocal_rank


def test_exact_match_identical():
    assert exact_match("9447", "9447") == 1


def test_exact_match_case_insensitive():
    assert exact_match("CTS", "cts") == 1


def test_exact_match_mismatch():
    assert exact_match("9447", "9448") == 0


def test_f1_perfect_match():
    assert f1_score("9447", "9447") == 1.0


def test_f1_partial_match():
    result = f1_score("Marketing, Logistics", "Marketing, R&D, Logistics")
    assert result == 0.8


def test_f1_no_overlap():
    assert f1_score("Marketing", "R&D") == 0.0


def test_numerical_accuracy_same_scale():
    assert numerical_accuracy(304811, 304811, scale="thousand") == 1


def test_numerical_accuracy_embedded_scale_in_prediction():
    assert numerical_accuracy("304.811 million", 304811, scale="thousand") == 1


def test_numerical_accuracy_parentheses_negative():
    assert numerical_accuracy("(9447)", -9447, scale=None) == 1


def test_numerical_accuracy_per_cent_phrase():
    assert numerical_accuracy("0 percent", "0 per cent", scale="") == 1


def test_numerical_accuracy_wrong_value():
    assert numerical_accuracy(100, 304811, scale="thousand") == 0

def test_recall_at_k_partial_match():
    assert retrieval_recall_at_k(["doc_041", "doc_099"], ["doc_017", "doc_041", "doc_005"], k=3) == 0.5


def test_recall_at_k_no_gold_docs():
    assert retrieval_recall_at_k([], ["doc_017"], k=3) == 1.0


def test_precision_at_k_partial_match():
    assert retrieval_precision_at_k(["doc_041", "doc_099"], ["doc_017", "doc_041", "doc_005"], k=3) == pytest.approx(1/3)


def test_precision_at_k_empty_results():
    assert retrieval_precision_at_k(["doc_041"], [], k=3) == 0.0


def test_reciprocal_rank_second_place():
    assert reciprocal_rank(["doc_041", "doc_099"], ["doc_017", "doc_041", "doc_005"]) == 0.5


def test_reciprocal_rank_never_found():
    assert reciprocal_rank(["doc_099"], ["doc_017", "doc_041", "doc_005"]) == 0.0
