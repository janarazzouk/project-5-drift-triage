from app.core.errors import UnknownJobTypeError
from app.jobs.base import BaseJob, ToolResult
from app.schemas.job import WorkerJobEnvelope


class JobRouter:
    def __init__(
        self,
        *,
        handlers: dict[str, BaseJob],
    ):
        self.handlers = handlers

    def run(
        self,
        job: WorkerJobEnvelope,
    ) -> ToolResult:
        handler = self.handlers.get(job.job_type)

        if handler is None:
            raise UnknownJobTypeError(f"Unknown job_type: {job.job_type}")

        return handler.run(job)