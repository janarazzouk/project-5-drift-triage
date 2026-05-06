# Drift Triage Agent

This service receives drift severity webhooks from the model service, opens investigations, runs a LangGraph supervisor workflow, dispatches slow jobs to Redis, and pauses for human approval before Production actions.

## Main responsibilities

- Receive drift webhooks from `model_service`
- Validate the drift webhook contract
- Create idempotent investigations
- Run supervisor flow with triage, action, and comms nodes
- Persist investigation state and LangGraph checkpoints in Postgres
- Dispatch replay, retrain, and rollback jobs to Redis
- Expose dashboard APIs for investigations, approvals, and queue status

## Run locally

From inside `agent/`:

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8010