from functools import lru_cache
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import (
    build_session_factory,
    init_db,
    save_or_update_reference_statistics,
    save_or_update_registry_state,
)
from app.drift import DriftService
from app.predict import Predictor
from app.registry import RegistryClient


@lru_cache
def get_predictor() -> Predictor:
    settings = get_settings()
    return Predictor(settings)


@lru_cache
def get_drift_service() -> DriftService:
    settings = get_settings()
    return DriftService(settings)


@lru_cache
def get_registry_client() -> RegistryClient:
    settings = get_settings()
    predictor = get_predictor()
    return RegistryClient(settings, predictor)


@lru_cache
def get_session_factory() -> sessionmaker:
    settings = get_settings()
    return build_session_factory(settings)


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    db = session_factory()

    try:
        yield db
    finally:
        db.close()


def initialize_resources() -> None:
    settings = get_settings()

    init_db(settings)

    predictor = get_predictor()
    drift_service = get_drift_service()
    registry_client = get_registry_client()

    session_factory = get_session_factory()
    db = session_factory()

    try:
        registry_info = registry_client.get_model_info()

        save_or_update_registry_state(
            db,
            model_name=registry_info["model_name"],
            model_version=registry_info["model_version"],
            model_stage="local",
            artifact_uri=registry_info["artifact_paths"].get("model"),
            selected_threshold=registry_info["threshold"],
            metrics=registry_info["metrics"],
        )

        save_or_update_reference_statistics(
            db,
            model_name=registry_info["model_name"],
            model_version=predictor.model_version,
            stats=drift_service.reference_stats,
        )

    finally:
        db.close()