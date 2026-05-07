import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ARTIFACT_FILES = [
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [json_safe(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


def save_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(json_safe(data), file, indent=2)
        file.write("\n")


def archive_existing_artifacts(artifact_dir: Path, *, enabled: bool) -> Path | None:
    if not enabled or not artifact_dir.exists():
        return None

    existing_files = [artifact_dir / filename for filename in ARTIFACT_FILES]
    existing_files = [path for path in existing_files if path.exists()]

    if not existing_files:
        return None

    archive_dir = artifact_dir / "archive" / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    for source in existing_files:
        shutil.copy2(source, archive_dir / source.name)

    return archive_dir