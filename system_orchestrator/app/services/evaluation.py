from typing import Any, Dict


def compute_precision_recall_f1(predicted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    if not ground_truth:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    true_positives = 0
    predicted_positives = 0
    actual_positives = 0

    for key, actual_value in ground_truth.items():
        expected_present = actual_value is not None
        predicted_value = predicted.get(key)
        predicted_present = predicted_value is not None

        if predicted_present:
            predicted_positives += 1
        if expected_present:
            actual_positives += 1
        if expected_present and predicted_present and predicted_value == actual_value:
            true_positives += 1

    precision = true_positives / predicted_positives if predicted_positives else 0.0
    recall = true_positives / actual_positives if actual_positives else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
