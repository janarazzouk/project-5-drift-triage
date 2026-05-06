from fastapi import FastAPI

from app.core.dependencies import initialize_resources
from app.routers import (
    drift,
    health,
    predict,
    promotion,
    registry,
    replay_compare,
    replay_fixture,
)


app = FastAPI(
    title="Drift Triage Model Service",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    initialize_resources()


app.include_router(health.router)
app.include_router(predict.router)
app.include_router(registry.router)
app.include_router(drift.router)
app.include_router(replay_fixture.router)
app.include_router(replay_compare.router)
app.include_router(promotion.router)