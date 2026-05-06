class AppError(Exception):
    status_code = 500
    error_code = "app_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ContractValidationError(AppError):
    status_code = 422
    error_code = "contract_validation_error"


class DuplicateEventError(AppError):
    status_code = 200
    error_code = "duplicate_event"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class InvalidStateError(AppError):
    status_code = 409
    error_code = "invalid_state"


class ApprovalRequiredError(AppError):
    status_code = 409
    error_code = "approval_required"


class QueueError(AppError):
    status_code = 500
    error_code = "queue_error"


class ExternalServiceError(AppError):
    status_code = 502
    error_code = "external_service_error"