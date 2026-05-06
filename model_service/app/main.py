import json
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import (
    save_drift_check,
    save_or_update_reference_statistics,
    save_or_update_registry_state,
    save_prediction,
)
from app.dependencies import (
    get_db,
    get_drift_service,
    get_predictor,
    get_registry_client,
    initialize_resources,
)
from app.drift import DriftService
from app.predict import Predictor
from app.registry import RegistryClient
from app.schemas import (
    DriftResponse,
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
    RegistryResponse,
    ReplayComparisonResponse,
    ReplayFixtureResponse,
)


app = FastAPI(
    title="Drift Triage Model Service",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    initialize_resources()


@app.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    predictor: Predictor = Depends(get_predictor),
) -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        version=settings.service_version,
        status="ok",
        model_loaded=predictor.model is not None,
        timestamp=datetime.utcnow(),
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    predictor: Predictor = Depends(get_predictor),
) -> PredictionResponse:
    try:
        result = predictor.predict(
            features=payload.features,
            request_id=payload.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    save_prediction(
        db,
        request_id=result["request_id"],
        features=result["features"],
        probability=result["probability"],
        predicted_class=result["predicted_class"],
        threshold=result["threshold"],
        model_version=result["model_version"],
    )

    return PredictionResponse(
        request_id=result["request_id"],
        probability=result["probability"],
        predicted_class=result["predicted_class"],
        threshold=result["threshold"],
        model_version=result["model_version"],
        saved=True,
    )


@app.get("/registry", response_model=RegistryResponse)
def registry(
    db: Session = Depends(get_db),
    registry_client: RegistryClient = Depends(get_registry_client),
) -> RegistryResponse:
    info = registry_client.get_model_info()

    save_or_update_registry_state(
        db,
        model_name=info["model_name"],
        model_version=info["model_version"],
        model_stage="local",
        artifact_uri=info["artifact_paths"].get("model"),
        selected_threshold=info["threshold"],
        metrics=info["metrics"],
    )

    return RegistryResponse(
        model_name=info["model_name"],
        model_version=info["model_version"],
        threshold=info["threshold"],
        metrics=info["metrics"],
        environment=info["environment"],
        artifact_paths=info["artifact_paths"],
    )


@app.get("/drift", response_model=DriftResponse)
def drift(
    db: Session = Depends(get_db),
    predictor: Predictor = Depends(get_predictor),
    registry_client: RegistryClient = Depends(get_registry_client),
    drift_service: DriftService = Depends(get_drift_service),
) -> DriftResponse:
    registry_info = registry_client.get_model_info()

    save_or_update_reference_statistics(
        db,
        model_name=registry_info["model_name"],
        model_version=predictor.model_version,
        stats=drift_service.reference_stats,
    )

    result = drift_service.analyze(db)

    save_drift_check(
        db,
        sample_size=result["sample_size"],
        overall_score=result["overall_score"],
        severity=result["severity"],
        details=result,
    )

    return DriftResponse(**result)


@app.get("/replay-fixture", response_model=ReplayFixtureResponse)
def replay_fixture(
    settings: Settings = Depends(get_settings),
) -> ReplayFixtureResponse:
    with open(settings.resolved_replay_fixture_path, "r", encoding="utf-8") as file:
        fixture_payload = json.load(file)

    fixture = fixture_payload.get("fixture", fixture_payload)

    return ReplayFixtureResponse(fixture=fixture)


@app.get("/replay-fixture/compare", response_model=ReplayComparisonResponse)
def replay_fixture_compare(
    settings: Settings = Depends(get_settings),
    predictor: Predictor = Depends(get_predictor),
) -> ReplayComparisonResponse:
    with open(settings.resolved_replay_fixture_path, "r", encoding="utf-8") as file:
        fixture_payload = json.load(file)

    fixture = fixture_payload.get("fixture", fixture_payload)

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

    return ReplayComparisonResponse(
        total_rows=len(rows),
        threshold=predictor.threshold,
        max_probability_difference=max_probability_difference,
        prediction_mismatches=prediction_mismatches,
        results=results,
    )