from typing import Any

from sqlalchemy.orm import Session

from app.contracts.drift_webhook import DriftWebhookPayload
from app.models.drift_event import DriftEvent


class DriftEventRepository:
    def get_by_event_id(
        self,
        db: Session,
        event_id: str,
    ) -> DriftEvent | None:
        return (
            db.query(DriftEvent)
            .filter(DriftEvent.event_id == event_id)
            .first()
        )

    def exists(
        self,
        db: Session,
        event_id: str,
    ) -> bool:
        return self.get_by_event_id(db, event_id) is not None

    def create_from_webhook(
        self,
        db: Session,
        payload: DriftWebhookPayload,
    ) -> DriftEvent:
        drift_report = payload.drift_report

        if hasattr(drift_report, "model_dump"):
            drift_report_json = drift_report.model_dump(mode="json")
        else:
            drift_report_json = drift_report

        record = DriftEvent(
            event_id=payload.event_id,
            contract_version=payload.contract_version,
            event_type=payload.event_type,
            source_service=payload.source_service,
            model_name=payload.model_name,
            model_version=payload.model_version,
            previous_severity=payload.previous_severity,
            new_severity=payload.new_severity,
            overall_score=payload.overall_score,
            sample_size=payload.sample_size,
            min_required_samples=payload.min_required_samples,
            drift_report_json=drift_report_json,
            metadata_json=payload.metadata,
            created_at=payload.created_at,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def list_recent(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DriftEvent]:
        return (
            db.query(DriftEvent)
            .order_by(DriftEvent.received_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session,
    ) -> int:
        return db.query(DriftEvent).count()

    def list_by_model_version(
        self,
        db: Session,
        *,
        model_name: str,
        model_version: str | None,
        limit: int = 50,
    ) -> list[DriftEvent]:
        query = db.query(DriftEvent).filter(DriftEvent.model_name == model_name)

        if model_version is None:
            query = query.filter(DriftEvent.model_version.is_(None))
        else:
            query = query.filter(DriftEvent.model_version == model_version)

        return (
            query.order_by(DriftEvent.received_at.desc())
            .limit(limit)
            .all()
        )

    def update_metadata(
        self,
        db: Session,
        *,
        event_id: str,
        metadata: dict[str, Any],
    ) -> DriftEvent | None:
        record = self.get_by_event_id(db, event_id)

        if record is None:
            return None

        current_metadata = record.metadata_json or {}
        current_metadata.update(metadata)
        record.metadata_json = current_metadata

        db.commit()
        db.refresh(record)

        return record