import pytest

from app.services.evaluation import compute_precision_recall_f1


def test_evaluation_metrics_exact_match():
    predicted = {
        "name": "Alice",
        "age": 30,
    }

    ground_truth = {
        "name": "Alice",
        "age": 30,
    }

    metrics = compute_precision_recall_f1(
        predicted,
        ground_truth,
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_evaluation_metrics_partial_match():
    predicted = {
        "name": "Alice",
        "age": None,
    }

    ground_truth = {
        "name": "Alice",
        "age": 30,
    }

    metrics = compute_precision_recall_f1(
        predicted,
        ground_truth,
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == pytest.approx(
        0.6666667,
        rel=1e-5,
    )