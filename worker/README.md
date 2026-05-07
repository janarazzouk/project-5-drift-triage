# Drift Triage Worker

The worker consumes Redis jobs created by the agent and executes slow tools.

## Responsibilities

- Read jobs from Redis
- Execute `replay_test`, `retrain`, and `rollback`
- Use idempotency keys to avoid duplicate execution
- Retry failed jobs with exponential backoff
- Move permanently failed jobs to DLQ
- Report job results back to the agent

## Run locally

```bash
cd worker
uv sync
uv run python -m app.main