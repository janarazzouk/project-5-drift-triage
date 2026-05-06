from pydantic import BaseModel


class ReplayComparisonItem(BaseModel):
    index: int
    request_id: str
    expected_probability: float | None = None
    actual_probability: float
    probability_difference: float | None = None
    expected_prediction: int | None = None
    actual_prediction: int
    prediction_matches: bool | None = None


class ReplayComparisonResponse(BaseModel):
    total_rows: int
    threshold: float
    max_probability_difference: float | None = None
    prediction_mismatches: int
    results: list[ReplayComparisonItem]