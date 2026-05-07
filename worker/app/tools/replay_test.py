from app.clients.model_service_client import ModelServiceClient
from app.schemas.replay_test import ReplayTestResult


class ReplayTestTool:
    def __init__(
        self,
        *,
        model_service_client: ModelServiceClient,
    ):
        self.model_service_client = model_service_client

    def run(self) -> ReplayTestResult:
        raw_result = self.model_service_client.get_replay_comparison()

        prediction_mismatches = raw_result.get("prediction_mismatches", 0)
        max_probability_difference = raw_result.get("max_probability_difference")

        passed = prediction_mismatches == 0

        return ReplayTestResult(
            passed=passed,
            total_rows=raw_result.get("total_rows", 0),
            threshold=raw_result.get("threshold", 0.0),
            max_probability_difference=max_probability_difference,
            prediction_mismatches=prediction_mismatches,
            raw_result=raw_result,
        )