import subprocess
from pathlib import Path

from app.schemas.retrain import RetrainResult


class RetrainTool:
    def __init__(
        self,
        *,
        command: str,
        working_dir: Path,
        timeout_seconds: int,
    ):
        self.command = command
        self.working_dir = working_dir
        self.timeout_seconds = timeout_seconds

    def run(self) -> RetrainResult:
        completed = subprocess.run(
            self.command,
            cwd=self.working_dir,
            shell=True,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )

        return RetrainResult(
            completed=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout_tail=completed.stdout[-4000:],
            stderr_tail=completed.stderr[-4000:],
        )