from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.contracts.drift_webhook import DriftWebhookPayload, DriftWebhookResponse
from app.core.deps import get_db, get_webhook_service
from app.core.errors import ContractValidationError
from app.services.webhook_service import WebhookService


router = APIRouter(tags=["webhooks"])


@router.post(
    "/webhooks/drift",
    response_model=DriftWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_drift_webhook(
    payload: DriftWebhookPayload,
    db: Session = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> DriftWebhookResponse:
    if x_contract_version is not None and x_contract_version != payload.contract_version:
        raise ContractValidationError(
            "X-Contract-Version does not match payload contract_version."
        )

    if x_idempotency_key is not None and x_idempotency_key != payload.event_id:
        raise ContractValidationError(
            "X-Idempotency-Key does not match payload event_id."
        )

    return webhook_service.process_drift_webhook(
        db=db,
        payload=payload,
    )