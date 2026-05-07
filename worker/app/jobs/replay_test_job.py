from app.jobs.base import BaseJob, ToolResult
from app.schemas.job import WorkerJobEnvelope
from app.tools.replay_test import ReplayTestTool


class ReplayTestJob(BaseJob):
    def __init__(
        self,
        replay_test_tool: ReplayTestTool,
    ):
        self.replay_test_tool = replay_test_tool

    def run(
        self,
        job: WorkerJobEnvelope,
    ) -> ToolResult:
        result = self.replay_test_tool.run()

        return ToolResult(
            success=result.passed,
            result=result.model_dump(mode="json"),
            error_message=(
                None
                if result.passed
                else "Replay test failed because prediction mismatches were found."
            ),
        )