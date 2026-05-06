import json
from typing import Any

from app.core.config import Settings
from app.services.prediction_service import Predictor


def load_replay_fixture(settings: Settings) -> dict[str, Any]:
    with open(settings.resolved_replay_fixture_path, "r", encoding="utf-8") as file:
        fixture_payload = json.load(file)

    return fixture_payload.get("fixture", fixture_payload)


def compare_replay_fixture(
    settings: Settings,
    predictor: Predictor,
) -> dict[str, Any]:
    fixture = load_replay_fixture(settings)

    rows = fixture.get("rows", [])
    expected_probabilities = fixture.get("expected_probabilities", [])
    expected_predictions = fixture.get("expected_predictions", [])

    results = []
    max_probability_difference = 0.0
    prediction_mismatches = 0

    for index, row in enumerate(rows):
        prediction_result = predictor.predict(
            features=row,
            request_id=f"replay-{index + 1}",
        )

        actual_probability = prediction_result["probability"]
        actual_prediction = prediction_result["predicted_class"]

        expected_probability = (
            expected_probabilities[index]
            if index < len(expected_probabilities)
            else None
        )

        expected_prediction = (
            expected_predictions[index]
            if index < len(expected_predictions)
            else None
        )

        probability_difference = None

        if expected_probability is not None:
            probability_difference = abs(actual_probability - expected_probability)
            max_probability_difference = max(
                max_probability_difference,
                probability_difference,
            )

        prediction_matches = None

        if expected_prediction is not None:
            prediction_matches = actual_prediction == expected_prediction

            if not prediction_matches:
                prediction_mismatches += 1

        results.append(
            {
                "index": index,
                "request_id": prediction_result["request_id"],
                "expected_probability": expected_probability,
                "actual_probability": actual_probability,
                "probability_difference": probability_difference,
                "expected_prediction": expected_prediction,
                "actual_prediction": actual_prediction,
                "prediction_matches": prediction_matches,
            }
        )

    return {
        "total_rows": len(rows),
        "threshold": predictor.threshold,
        "max_probability_difference": max_probability_difference,
        "prediction_mismatches": prediction_mismatches,
        "results": results,
    }