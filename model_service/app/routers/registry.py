from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import save_or_update_registry_state
from app.core.dependencies import get_db, get_registry_client
from app.schemas.registry import RegistryResponse
from app.services.registry_service import RegistryClient


router = APIRouter(tags=["registry"])


@router.get("/registry", response_model=RegistryResponse)
def registry(
    db: Session = Depends(get_db),
    registry_client: RegistryClient = Depends(get_registry_client),
) -> RegistryResponse:
    info = registry_client.get_model_info()

    save_or_update_registry_state(
        db,
        model_name=info["model_name"],
        model_version=info["model_version"],
        model_stage="local",
        artifact_uri=info["artifact_paths"].get("model"),
        selected_threshold=info["threshold"],
        metrics=info["metrics"],
    )

    return RegistryResponse(
        model_name=info["model_name"],
        model_version=info["model_version"],
        threshold=info["threshold"],
        metrics=info["metrics"],
        environment=info["environment"],
        artifact_paths=info["artifact_paths"],
    )