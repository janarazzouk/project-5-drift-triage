from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.investigation import Investigation


class InvestigationRepository:
    def get_by_id(
        self,
        db: Session,
        investigation_id: str,
    ) -> Investigation | None:
        return (
            db.query(Investigation)
            .filter(Investigation.id == investigation_id)
            .first()
        )

    def get_by_event_id(
        self,
        db: Session,
        event_id: str,
    ) -> Investigation | None:
        return (
            db.query(Investigation)
            .filter(Investigation.event_id == event_id)
            .first()
        )

    def get_by_thread_id(
        self,
        db: Session,
        graph_thread_id: str,
    ) -> Investigation | None:
        return (
            db.query(Investigation)
            .filter(Investigation.graph_thread_id == graph_thread_id)
            .first()
        )

    def create(
        self,
        db: Session,
        *,
        investigation_id: str,
        event_id: str,
        model_name: str,
        model_version: str | None,
        severity: str,
        graph_thread_id: str,
        state: dict[str, Any],
    ) -> Investigation:
        record = Investigation(
            id=investigation_id,
            event_id=event_id,
            model_name=model_name,
            model_version=model_version,
            severity=severity,
            status="open",
            current_step="created",
            graph_thread_id=graph_thread_id,
            state_json=state,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def update_state(
        self,
        db: Session,
        *,
        investigation_id: str,
        status: str | None = None,
        current_step: str | None = None,
        recommended_action: str | None = None,
        production_action_required: bool | None = None,
        approval_id: str | None = None,
        summary: str | None = None,
        state: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> Investigation | None:
        record = self.get_by_id(db, investigation_id)

        if record is None:
            return None

        if status is not None:
            record.status = status

        if current_step is not None:
            record.current_step = current_step

        if recommended_action is not None:
            record.recommended_action = recommended_action

        if production_action_required is not None:
            record.production_action_required = production_action_required

        if approval_id is not None:
            record.approval_id = approval_id

        if summary is not None:
            record.summary = summary

        if state is not None:
            record.state_json = state

        if result is not None:
            record.result_json = result

        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_running(
        self,
        db: Session,
        *,
        investigation_id: str,
        current_step: str,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        return self.update_state(
            db,
            investigation_id=investigation_id,
            status="running",
            current_step=current_step,
            state=state,
        )

    def mark_waiting_for_job(
        self,
        db: Session,
        *,
        investigation_id: str,
        recommended_action: str,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        return self.update_state(
            db,
            investigation_id=investigation_id,
            status="waiting_for_job",
            current_step="waiting_for_job",
            recommended_action=recommended_action,
            production_action_required=False,
            state=state,
        )

    def mark_waiting_for_approval(
        self,
        db: Session,
        *,
        investigation_id: str,
        approval_id: str,
        recommended_action: str,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        return self.update_state(
            db,
            investigation_id=investigation_id,
            status="waiting_for_approval",
            current_step="waiting_for_approval",
            recommended_action=recommended_action,
            production_action_required=True,
            approval_id=approval_id,
            state=state,
        )

    def resolve(
        self,
        db: Session,
        *,
        investigation_id: str,
        summary: str,
        result: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        record = self.get_by_id(db, investigation_id)

        if record is None:
            return None

        record.status = "resolved"
        record.current_step = "completed"
        record.summary = summary
        record.result_json = result
        record.state_json = state or record.state_json
        record.resolved_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def fail(
        self,
        db: Session,
        *,
        investigation_id: str,
        summary: str,
        result: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        record = self.get_by_id(db, investigation_id)

        if record is None:
            return None

        record.status = "failed"
        record.current_step = "failed"
        record.summary = summary
        record.result_json = result
        record.state_json = state or record.state_json
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def list_recent(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Investigation]:
        query = db.query(Investigation)

        if status is not None:
            query = query.filter(Investigation.status == status)

        return (
            query.order_by(Investigation.opened_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session,
        *,
        status: str | None = None,
    ) -> int:
        query = db.query(Investigation)

        if status is not None:
            query = query.filter(Investigation.status == status)

        return query.count()

    def list_open(
        self,
        db: Session,
        *,
        limit: int = 50,
    ) -> list[Investigation]:
        return (
            db.query(Investigation)
            .filter(Investigation.status.in_(["open", "running", "waiting_for_job", "waiting_for_approval"]))
            .order_by(Investigation.opened_at.desc())
            .limit(limit)
            .all()
        )