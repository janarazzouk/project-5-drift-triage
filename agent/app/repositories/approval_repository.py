from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.approval import Approval


class ApprovalRepository:
    def get_by_id(
        self,
        db: Session,
        approval_id: str,
    ) -> Approval | None:
        return (
            db.query(Approval)
            .filter(Approval.id == approval_id)
            .first()
        )

    def list_by_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> list[Approval]:
        return (
            db.query(Approval)
            .filter(Approval.investigation_id == investigation_id)
            .order_by(Approval.created_at.desc())
            .all()
        )

    def list_pending(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Approval]:
        return (
            db.query(Approval)
            .filter(Approval.status == "pending")
            .order_by(Approval.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_recent(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Approval]:
        query = db.query(Approval)

        if status is not None:
            query = query.filter(Approval.status == status)

        return (
            query.order_by(Approval.created_at.desc())
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
        query = db.query(Approval)

        if status is not None:
            query = query.filter(Approval.status == status)

        return query.count()

    def create(
        self,
        db: Session,
        *,
        approval_id: str,
        investigation_id: str,
        requested_action: str,
        target_environment: str,
        model_name: str,
        model_version: str | None,
        reason: str,
        request_payload: dict[str, Any] | None = None,
    ) -> Approval:
        record = Approval(
            id=approval_id,
            investigation_id=investigation_id,
            requested_action=requested_action,
            target_environment=target_environment,
            model_name=model_name,
            model_version=model_version,
            status="pending",
            reason=reason,
            request_payload_json=request_payload,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def approve(
        self,
        db: Session,
        *,
        approval_id: str,
        approved_by: str,
        decision_payload: dict[str, Any] | None = None,
    ) -> Approval | None:
        record = self.get_by_id(db, approval_id)

        if record is None:
            return None

        record.status = "approved"
        record.approved = True
        record.approved_by = approved_by
        record.approved_at = datetime.utcnow()
        record.decision_payload_json = decision_payload
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def reject(
        self,
        db: Session,
        *,
        approval_id: str,
        rejected_by: str,
        rejection_reason: str,
        decision_payload: dict[str, Any] | None = None,
    ) -> Approval | None:
        record = self.get_by_id(db, approval_id)

        if record is None:
            return None

        record.status = "rejected"
        record.approved = False
        record.rejected_by = rejected_by
        record.rejected_at = datetime.utcnow()
        record.rejection_reason = rejection_reason
        record.decision_payload_json = decision_payload
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def expire(
        self,
        db: Session,
        *,
        approval_id: str,
        reason: str = "Approval expired.",
    ) -> Approval | None:
        record = self.get_by_id(db, approval_id)

        if record is None:
            return None

        record.status = "expired"
        record.approved = False
        record.rejection_reason = reason
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record