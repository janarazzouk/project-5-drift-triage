from app.jobs.base import BaseJob, ToolResult
from app.schemas.job import WorkerJobEnvelope
from app.tools.rollback import RollbackTool


class RollbackJob(BaseJob):
    def __init__(
        self,
        rollback_tool: RollbackTool,
    ):
        self.rollback_tool = rollback_tool

    def run(
        self,
        job: WorkerJobEnvelope,
    ) -> ToolResult:
        result = self.rollback_tool.run(job.payload)

        return ToolResult(
            success=result.completed,
            result=result.model_dump(mode="json"),
            error_message=(
                None
                if result.completed
                else "Rollback did not complete successfully."
            ),
        )