import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.retrain import RetrainResult


REQUIRED_RETRAIN_ARTIFACTS = [
    "model_pipeline.joblib",
    "schema.json",
    "runtime_config.json",
    "reference_stats.json",
    "replay_fixture.json",
    "metrics.json",
    "environment.json",
    "model_card.md",
    "training_summary.json",
]


class RetrainTool:
    def __init__(
        self,
        *,
        command: str,
        working_dir: Path,
        timeout_seconds: int,
    ):
        self.command = command
        self.working_dir = Path(working_dir)
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        *,
        job_payload: dict[str, Any] | None = None,
    ) -> RetrainResult:
        job_payload = job_payload or {}

        started_epoch = time.time()
        started_monotonic = time.monotonic()
        started_at = _utc_now()

        stdout = ""
        stderr = ""
        exit_code: int | None = None

        try:
            completed_process = subprocess.run(
                self.command,
                cwd=self.working_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

            exit_code = completed_process.returncode
            stdout = completed_process.stdout or ""
            stderr = completed_process.stderr or ""

        except subprocess.TimeoutExpired as exc:
            stdout = _to_text(exc.stdout)
            stderr = _to_text(exc.stderr)
            finished_at = _utc_now()

            return RetrainResult(
                completed=False,
                exit_code=None,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=round(time.monotonic() - started_monotonic, 3),
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                error_message=(
                    f"Retrain command timed out after "
                    f"{self.timeout_seconds} seconds."
                ),
            )

        finished_at = _utc_now()
        duration_seconds = round(time.monotonic() - started_monotonic, 3)

        if exit_code != 0:
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                error_message=(
                    "Retrain command failed. "
                    "The training script returned a non-zero exit code."
                ),
            )

        artifact_dir = self._find_artifact_dir(
            job_payload=job_payload,
            stdout=stdout,
        )
        summary_path = artifact_dir / "training_summary.json"

        if not summary_path.exists():
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                training_summary_found=False,
                training_summary_path=str(summary_path),
                artifact_dir=str(artifact_dir),
                error_message=(
                    "Retrain command exited successfully, but "
                    "training_summary.json was not found. "
                    "The worker cannot verify that a real candidate model was produced."
                ),
            )

        try:
            training_summary = _read_json(summary_path)
        except json.JSONDecodeError as exc:
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                training_summary_found=True,
                training_summary_path=str(summary_path),
                artifact_dir=str(artifact_dir),
                error_message=f"training_summary.json is invalid JSON: {exc}",
            )

        missing_artifacts, stale_artifacts, produced_artifacts = self._validate_artifacts(
            artifact_dir=artifact_dir,
            started_epoch=started_epoch,
        )

        if missing_artifacts:
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                training_summary_found=True,
                training_summary_path=str(summary_path),
                artifact_dir=str(artifact_dir),
                missing_artifacts=missing_artifacts,
                stale_artifacts=stale_artifacts,
                produced_artifacts=produced_artifacts,
                training_summary=training_summary,
                error_message=(
                    "Retrain command exited successfully, but required artifacts "
                    "are missing."
                ),
            )

        if stale_artifacts:
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                training_summary_found=True,
                training_summary_path=str(summary_path),
                artifact_dir=str(artifact_dir),
                missing_artifacts=missing_artifacts,
                stale_artifacts=stale_artifacts,
                produced_artifacts=produced_artifacts,
                training_summary=training_summary,
                error_message=(
                    "Retrain command exited successfully, but some artifacts look stale. "
                    "The worker will not mark this retrain as completed."
                ),
            )

        if not bool(training_summary.get("completed")):
            return RetrainResult(
                completed=False,
                exit_code=exit_code,
                command=self.command,
                working_dir=str(self.working_dir),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                stdout_tail=_tail(stdout),
                stderr_tail=_tail(stderr),
                training_summary_found=True,
                training_summary_path=str(summary_path),
                artifact_dir=str(artifact_dir),
                missing_artifacts=missing_artifacts,
                stale_artifacts=stale_artifacts,
                produced_artifacts=produced_artifacts,
                training_summary=training_summary,
                error_message=(
                    "training_summary.json exists, but it does not say "
                    "completed=true."
                ),
            )

        return RetrainResult(
            completed=True,
            exit_code=exit_code,
            command=self.command,
            working_dir=str(self.working_dir),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            stdout_tail=_tail(stdout),
            stderr_tail=_tail(stderr),
            training_summary_found=True,
            training_summary_path=str(summary_path),
            artifact_dir=str(artifact_dir),
            missing_artifacts=missing_artifacts,
            stale_artifacts=stale_artifacts,
            produced_artifacts=produced_artifacts,
            archived_previous_artifacts_dir=training_summary.get(
                "archived_previous_artifacts_dir"
            ),
            registered_model_name=training_summary.get("registered_model_name"),
            model_version=_to_optional_string(training_summary.get("model_version")),
            mlflow_run_id=training_summary.get("mlflow_run_id"),
            mlflow_model_uri=training_summary.get("mlflow_model_uri"),
            selected_threshold=training_summary.get("selected_threshold"),
            test_metrics=training_summary.get("test_metrics") or {},
            training_summary=training_summary,
        )

    def _find_artifact_dir(
        self,
        *,
        job_payload: dict[str, Any],
        stdout: str,
    ) -> Path:
        candidates: list[Path] = []

        payload_artifact_dir = job_payload.get("artifact_dir")
        if payload_artifact_dir:
            candidates.append(self._resolve_artifact_dir(payload_artifact_dir))

        payload_summary_path = job_payload.get("training_summary_path")
        if payload_summary_path:
            candidates.append(self._resolve_artifact_dir(Path(payload_summary_path).parent))

        stdout_artifact_dir = _parse_artifact_dir_from_stdout(stdout)
        if stdout_artifact_dir:
            candidates.append(self._resolve_artifact_dir(stdout_artifact_dir))

        for env_name in [
            "TRAINING_ARTIFACT_DIR",
            "ARTIFACT_DIR",
            "MODEL_SERVICE_ARTIFACT_DIR",
        ]:
            env_value = os.getenv(env_name) or self._read_env_value(env_name)
            if env_value:
                candidates.append(self._resolve_artifact_dir(env_value))

        candidates.append(self.working_dir / "artifacts")

        for candidate in _dedupe_paths(candidates):
            if (candidate / "training_summary.json").exists():
                return candidate

        return candidates[0] if candidates else self.working_dir / "artifacts"

    def _resolve_artifact_dir(
        self,
        value: str | Path,
    ) -> Path:
        path = Path(value).expanduser()

        if path.is_absolute():
            return path

        project_root = self.working_dir.parent

        if path.parts and path.parts[0] == "model_service":
            return project_root / path

        return self.working_dir / path

    def _read_env_value(
        self,
        name: str,
    ) -> str | None:
        for env_file in [self.working_dir.parent / ".env", self.working_dir / ".env"]:
            value = _read_simple_env_file_value(env_file, name)

            if value:
                return value

        return None

    def _validate_artifacts(
        self,
        *,
        artifact_dir: Path,
        started_epoch: float,
    ) -> tuple[list[str], list[str], list[str]]:
        missing_artifacts: list[str] = []
        stale_artifacts: list[str] = []
        produced_artifacts: list[str] = []

        for filename in REQUIRED_RETRAIN_ARTIFACTS:
            path = artifact_dir / filename

            if not path.exists():
                missing_artifacts.append(filename)
                continue

            produced_artifacts.append(filename)

            # Small tolerance avoids false failures from filesystem timestamp precision.
            if path.stat().st_mtime < started_epoch - 2:
                stale_artifacts.append(filename)

        return missing_artifacts, stale_artifacts, produced_artifacts


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if value else ""


def _to_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _parse_artifact_dir_from_stdout(stdout: str) -> str | None:
    match = re.search(r"Artifacts saved to:\s*(.+)", stdout)

    if not match:
        return None

    return match.group(1).strip()


def _to_optional_string(value: Any) -> str | None:
    if value is None:
        return None

    return str(value)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []

    for path in paths:
        resolved_key = str(path.expanduser())

        if resolved_key in seen:
            continue

        seen.add(resolved_key)
        unique.append(path)

    return unique


def _read_simple_env_file_value(
    env_file: Path,
    name: str,
) -> str | None:
    if not env_file.exists():
        return None

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        if key.strip() != name:
            continue

        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        return value

    return None