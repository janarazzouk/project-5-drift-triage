class RetryPolicy:
    def __init__(
        self,
        *,
        max_attempts: int,
        base_delay_seconds: int,
    ):
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def should_retry(
        self,
        attempts: int,
        max_attempts: int | None = None,
    ) -> bool:
        limit = max_attempts or self.max_attempts
        return attempts < limit

    def delay_seconds(
        self,
        attempts: int,
    ) -> int:
        return self.base_delay_seconds * (2 ** max(attempts - 1, 0))