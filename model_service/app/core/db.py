from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import (
    Base,
    DriftCheck,
    PredictionRecord,
    PromotionDecision,
    ReferenceStatistics,
    RegistryState,
    RollbackDecision,
)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [json_safe(item) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass

    if isinstance(value, float) and value != value:
        return None

    return value


def build_engine(settings: Settings):
    connect_args = {}

    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def build_session_factory(settings: Settings):
    engine = build_engine(settings)

    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


def init_db(settings: Settings) -> None:
    engine = build_engine(settings)
    Base.metadata.create_all(bind=engine)


def save_prediction(
    db: Session,
    *,
    request_id: str,
    features: dict,
    probability: float,
    predicted_class: int,
    threshold: float,
    model_version: str | None,
) -> PredictionRecord:
    record = PredictionRecord(
        request_id=request_id,
        features_json=json_safe(features),
        probability=probability,
        predicted_class=predicted_class,
        threshold=threshold,
        model_version=model_version,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_registry_state(
    db: Session,
    *,
    model_name: str,
    model_version: str | None,
) -> RegistryState | None:
    query = db.query(RegistryState).filter(
        RegistryState.model_name == model_name,
    )

    if model_version is None:
        query = query.filter(RegistryState.model_version.is_(None))
    else:
        query = query.filter(RegistryState.model_version == model_version)

    return query.first()


def save_or_update_registry_state(
    db: Session,
    *,
    model_name: str,
    model_version: str | None,
    model_stage: str | None,
    artifact_uri: str | None,
    selected_threshold: float,
    metrics: dict[str, Any],
) -> RegistryState:
    record = get_registry_state(
        db,
        model_name=model_name,
        model_version=model_version,
    )

    if record is None:
        record = RegistryState(
            model_name=model_name,
            model_version=model_version,
            model_stage=model_stage,
            artifact_uri=artifact_uri,
            selected_threshold=selected_threshold,
            metrics_json=json_safe(metrics),
        )
        db.add(record)
    else:
        record.model_stage = model_stage
        record.artifact_uri = artifact_uri
        record.selected_threshold = selected_threshold
        record.metrics_json = json_safe(metrics)
        record.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(record)

    return record


def save_or_update_reference_statistics(
    db: Session,
    *,
    model_name: str,
    model_version: str | None,
    stats: dict[str, Any],
) -> ReferenceStatistics:
    record = (
        db.query(ReferenceStatistics)
        .filter(
            ReferenceStatistics.model_name == model_name,
            ReferenceStatistics.model_version == model_version,
        )
        .first()
    )

    if record is None:
        record = ReferenceStatistics(
            model_name=model_name,
            model_version=model_version,
            stats_json=json_safe(stats),
        )
        db.add(record)
    else:
        record.stats_json = json_safe(stats)
        record.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(record)

    return record


def save_drift_check(
    db: Session,
    *,
    sample_size: int,
    overall_score: float,
    severity: str,
    details: dict[str, Any],
) -> DriftCheck:
    record = DriftCheck(
        sample_size=sample_size,
        overall_score=overall_score,
        severity=severity,
        details_json=json_safe(details),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_latest_drift_check(db: Session) -> DriftCheck | None:
    return db.query(DriftCheck).order_by(DriftCheck.created_at.desc()).first()


def get_existing_promotion_decision(
    db: Session,
    *,
    request_id: str,
) -> PromotionDecision | None:
    return (
        db.query(PromotionDecision)
        .filter(PromotionDecision.request_id == request_id)
        .first()
    )


def save_promotion_decision(
    db: Session,
    *,
    request_id: str,
    model_name: str,
    model_version: str | None,
    requested_action: str,
    target_environment: str,
    promoted: bool,
    message: str,
    checklist: dict[str, Any],
) -> PromotionDecision:
    record = PromotionDecision(
        request_id=request_id,
        model_name=model_name,
        model_version=model_version,
        requested_action=requested_action,
        target_environment=target_environment,
        promoted=promoted,
        message=message,
        checklist_json=json_safe(checklist),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_existing_rollback_decision(
    db: Session,
    *,
    request_id: str,
) -> RollbackDecision | None:
    return (
        db.query(RollbackDecision)
        .filter(RollbackDecision.request_id == request_id)
        .first()
    )


def save_rollback_decision(
    db: Session,
    *,
    request_id: str,
    investigation_id: str,
    approval_id: str,
    model_name: str,
    model_version: str | None,
    requested_action: str,
    target_environment: str,
    previous_stage: str | None,
    new_stage: str | None,
    rolled_back: bool,
    message: str,
    details: dict[str, Any],
) -> RollbackDecision:
    record = RollbackDecision(
        request_id=request_id,
        investigation_id=investigation_id,
        approval_id=approval_id,
        model_name=model_name,
        model_version=model_version,
        requested_action=requested_action,
        target_environment=target_environment,
        previous_stage=previous_stage,
        new_stage=new_stage,
        rolled_back=rolled_back,
        message=message,
        details_json=json_safe(details),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record