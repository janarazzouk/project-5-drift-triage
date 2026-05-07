from app.jobs.base import BaseJob, ToolResult
from app.schemas.job import WorkerJobEnvelope
from app.tools.retrain import RetrainTool


class RetrainJob(BaseJob):
    def __init__(
        self,
        retrain_tool: RetrainTool,
    ):
        self.retrain_tool = retrain_tool

    def run(
        self,
        job: WorkerJobEnvelope,
    ) -> ToolResult:
        result = self.retrain_tool.run()

        return ToolResult(
            success=result.completed,
            result=result.model_dump(mode="json"),
            error_message=(
                None
                if result.completed
                else "Retrain command failed. Check stderr_tail for details."
            ),
        )