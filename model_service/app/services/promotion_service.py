from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import (
    get_existing_promotion_decision,
    get_latest_drift_check,
    save_or_update_registry_state,
    save_promotion_decision,
)
from app.schemas.promotion import (
    PromotionCheckResult,
    PromotionChecklistResponse,
    PromotionRequest,
    PromotionResponse,
)
from app.services.prediction_service import Predictor
from app.services.registry_service import RegistryClient
from app.services.replay_service import compare_replay_fixture


class PromotionService:
    def __init__(
        self,
        settings: Settings,
        predictor: Predictor,
        registry_client: RegistryClient,
    ):
        self.settings = settings
        self.predictor = predictor
        self.registry_client = registry_client

    def run_checklist(
        self,
        db: Session,
        request: PromotionRequest | None = None,
    ) -> PromotionChecklistResponse:
        registry_info = self.registry_client.get_model_info()
        metrics = registry_info["metrics"]

        checks: list[PromotionCheckResult] = []

        checks.extend(self._artifact_checks())

        checks.append(
            PromotionCheckResult(
                name="model_loaded",
                passed=self.predictor.model is not None,
                message=(
                    "Model is loaded."
                    if self.predictor.model is not None
                    else "Model is not loaded."
                ),
            )
        )

        if request is not None:
            checks.extend(self._request_checks(request, registry_info))

        checks.extend(self._metric_checks(metrics))
        checks.extend(self._replay_checks())
        checks.append(self._latest_drift_check(db))

        passed = all(check.passed for check in checks)

        return PromotionChecklistResponse(
            passed=passed,
            checks=checks,
        )

    def request_production_promotion(
        self,
        db: Session,
        request: PromotionRequest,
    ) -> PromotionResponse:
        existing_decision = get_existing_promotion_decision(
            db,
            request_id=request.request_id,
        )

        if existing_decision is not None:
            return PromotionResponse(
                promoted=existing_decision.promoted,
                duplicate=True,
                request_id=existing_decision.request_id,
                model_name=existing_decision.model_name,
                model_version=existing_decision.model_version,
                target_environment=existing_decision.target_environment,
                message=existing_decision.message,
                checklist=PromotionChecklistResponse(**existing_decision.checklist_json),
            )

        checklist = self.run_checklist(db, request=request)
        registry_info = self.registry_client.get_model_info()

        promoted = checklist.passed

        if promoted:
            save_or_update_registry_state(
                db,
                model_name=registry_info["model_name"],
                model_version=registry_info["model_version"],
                model_stage="production",
                artifact_uri=registry_info["artifact_paths"].get("model"),
                selected_threshold=registry_info["threshold"],
                metrics=registry_info["metrics"],
            )

            message = "Model promoted to Production."
        else:
            message = "Promotion blocked because checklist failed."

        save_promotion_decision(
            db,
            request_id=request.request_id,
            model_name=request.model_name,
            model_version=request.model_version,
            requested_action=request.requested_action,
            target_environment=request.target_environment,
            promoted=promoted,
            message=message,
            checklist=checklist.model_dump(mode="json"),
        )

        return PromotionResponse(
            promoted=promoted,
            duplicate=False,
            request_id=request.request_id,
            model_name=request.model_name,
            model_version=request.model_version,
            target_environment=request.target_environment,
            message=message,
            checklist=checklist,
        )

    def _artifact_checks(self) -> list[PromotionCheckResult]:
        required_artifacts = {
            "model_artifact_exists": self.settings.resolved_model_path,
            "schema_artifact_exists": self.settings.resolved_schema_path,
            "runtime_config_artifact_exists": self.settings.resolved_runtime_config_path,
            "reference_stats_artifact_exists": self.settings.resolved_reference_stats_path,
            "metrics_artifact_exists": self.settings.resolved_metrics_path,
            "environment_artifact_exists": self.settings.resolved_environment_path,
            "replay_fixture_artifact_exists": self.settings.resolved_replay_fixture_path,
            "model_card_artifact_exists": self.settings.resolved_model_card_path,
        }

        checks = []

        for name, path in required_artifacts.items():
            artifact_path = Path(path)

            checks.append(
                PromotionCheckResult(
                    name=name,
                    passed=artifact_path.exists(),
                    message=(
                        f"Artifact exists: {artifact_path}"
                        if artifact_path.exists()
                        else f"Missing artifact: {artifact_path}"
                    ),
                )
            )

        return checks

    def _request_checks(
        self,
        request: PromotionRequest,
        registry_info: dict,
    ) -> list[PromotionCheckResult]:
        current_model_name = registry_info["model_name"]
        current_model_version = registry_info["model_version"]

        return [
            PromotionCheckResult(
                name="human_approval_present",
                passed=request.human_approval.approved is True,
                message="Human approval is present.",
            ),
            PromotionCheckResult(
                name="requested_model_name_matches_registry",
                passed=request.model_name == current_model_name,
                message=(
                    "Requested model name matches registry."
                    if request.model_name == current_model_name
                    else (
                        f"Requested model name '{request.model_name}' does not match "
                        f"current registry model name '{current_model_name}'."
                    )
                ),
            ),
            PromotionCheckResult(
                name="requested_model_version_matches_loaded_model",
                passed=request.model_version == current_model_version,
                message=(
                    "Requested model version matches loaded model."
                    if request.model_version == current_model_version
                    else (
                        f"Requested model version '{request.model_version}' does not match "
                        f"loaded model version '{current_model_version}'."
                    )
                ),
            ),
        ]

    def _metric_checks(self, metrics: dict) -> list[PromotionCheckResult]:
        checks = []

        metric_rules = [
            ("accuracy", self.settings.promotion_min_accuracy),
            ("precision", self.settings.promotion_min_precision),
            ("recall", self.settings.promotion_min_recall),
            ("f1", self.settings.promotion_min_f1),
            ("auc", self.settings.promotion_min_auc),
        ]

        for metric_name, minimum_value in metric_rules:
            value = self._get_metric(metrics, metric_name)

            if value is None:
                checks.append(
                    PromotionCheckResult(
                        name=f"metric_{metric_name}",
                        passed=False,
                        message=f"Missing metric: {metric_name}",
                    )
                )
                continue

            checks.append(
                PromotionCheckResult(
                    name=f"metric_{metric_name}",
                    passed=value >= minimum_value,
                    message=(
                        f"{metric_name}={value:.4f} passes minimum {minimum_value:.4f}."
                        if value >= minimum_value
                        else f"{metric_name}={value:.4f} is below minimum {minimum_value:.4f}."
                    ),
                )
            )

        return checks

    def _replay_checks(self) -> list[PromotionCheckResult]:
        try:
            replay_result = compare_replay_fixture(
                settings=self.settings,
                predictor=self.predictor,
            )
        except Exception as exc:
            return [
                PromotionCheckResult(
                    name="replay_fixture_compare",
                    passed=False,
                    message=f"Replay fixture comparison failed: {exc}",
                )
            ]

        prediction_mismatches = replay_result["prediction_mismatches"]
        max_probability_difference = replay_result["max_probability_difference"]

        return [
            PromotionCheckResult(
                name="replay_prediction_mismatches",
                passed=prediction_mismatches
                <= self.settings.promotion_max_replay_mismatches,
                message=(
                    f"Replay mismatches={prediction_mismatches} is within allowed limit "
                    f"{self.settings.promotion_max_replay_mismatches}."
                    if prediction_mismatches
                    <= self.settings.promotion_max_replay_mismatches
                    else (
                        f"Replay mismatches={prediction_mismatches} exceeds allowed limit "
                        f"{self.settings.promotion_max_replay_mismatches}."
                    )
                ),
            ),
            PromotionCheckResult(
                name="replay_probability_difference",
                passed=max_probability_difference
                <= self.settings.promotion_max_probability_difference,
                message=(
                    f"Max probability difference={max_probability_difference} is within allowed "
                    f"limit {self.settings.promotion_max_probability_difference}."
                    if max_probability_difference
                    <= self.settings.promotion_max_probability_difference
                    else (
                        f"Max probability difference={max_probability_difference} exceeds allowed "
                        f"limit {self.settings.promotion_max_probability_difference}."
                    )
                ),
            ),
        ]

    def _latest_drift_check(self, db: Session) -> PromotionCheckResult:
        latest_drift_check = get_latest_drift_check(db)

        if latest_drift_check is None:
            return PromotionCheckResult(
                name="latest_drift_severity",
                passed=False,
                message="No drift check found. Run /drift before Production promotion.",
            )

        allowed_severities = self.settings.promotion_allowed_drift_severity_set

        passed = latest_drift_check.severity in allowed_severities

        return PromotionCheckResult(
            name="latest_drift_severity",
            passed=passed,
            message=(
                f"Latest drift severity '{latest_drift_check.severity}' is allowed."
                if passed
                else (
                    f"Latest drift severity '{latest_drift_check.severity}' is not allowed. "
                    f"Allowed severities: {sorted(allowed_severities)}."
                )
            ),
        )

    def _get_metric(self, metrics: dict, metric_name: str) -> float | None:
        possible_keys = [
            f"test_{metric_name}",
            metric_name,
        ]

        for key in possible_keys:
            value = metrics.get(key)

            if value is not None:
                return float(value)

        return None