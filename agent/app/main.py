from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import approvals, health, investigations, queue, webhooks
from app.core.deps import get_checkpoint_service, initialize_resources
from app.core.errors import AppError
from app.core.logging import configure_logging


configure_logging()


app = FastAPI(
    title="Drift Triage Agent",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    initialize_resources()


@app.on_event("shutdown")
def shutdown() -> None:
    checkpoint_service = get_checkpoint_service()
    checkpoint_service.close()


@app.exception_handler(AppError)
def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
        },
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed.",
            "details": exc.errors(),
        },
    )


app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(investigations.router)
app.include_router(approvals.router)
app.include_router(queue.router)