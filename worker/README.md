# Worker Flow

The `worker/` folder contains the background worker that listens to Redis and executes slow drift-triage jobs. It is separate from the FastAPI services so long-running tasks do not block API requests.

The worker executes approved or queued actions, then reports the result back to the agent.

---

## Folder structure

```txt
worker/
├── app/
│   ├── clients/        # HTTP clients for agent and model service
│   ├── core/           # Settings, database, dependencies, errors, logging
│   ├── jobs/           # Job wrappers and job router
│   ├── models/         # SQLAlchemy worker job table
│   ├── queue/          # Redis consumer, producer, retry, DLQ, idempotency
│   ├── repositories/   # Database access for worker jobs
│   ├── schemas/        # Pydantic job/result schemas
│   ├── services/       # Job logging and result services
│   └── tools/          # Actual replay, retrain, rollback tools
├── worker.py
├── Dockerfile
└── pyproject.toml
```

---

## Main responsibility

The worker answers this question:

```txt
A safe action was queued. How do we execute it reliably and report the result?
```

It does this by:

1. Listening to the Redis queue.
2. Validating the job envelope.
3. Preventing duplicate execution with idempotency keys.
4. Running the correct job handler.
5. Retrying failed jobs.
6. Moving permanently failed jobs to the dead-letter queue.
7. Posting the final job result back to the agent.

---

## Worker loop flow

Entrypoint:

```txt
python -m app.main
```

Flow:

```txt
start worker
    ↓
load WORKER_ settings from .env
    ↓
initialize worker database tables
    ↓
connect to Redis
    ↓
listen for jobs on drift_triage_jobs
    ↓
move job to processing queue while running
    ↓
parse and validate job envelope
    ↓
acquire idempotency lock
    ↓
route job to matching handler
    ↓
execute tool
    ↓
notify agent with result
    ↓
remove job from processing queue
```

---

## Supported job types

| Job type | Handler | What it does |
|---|---|---|
| `replay_test` | `ReplayTestJob` | Calls model service replay comparison endpoint |
| `retrain` | `RetrainJob` | Runs the training command and validates fresh artifacts |
| `rollback` | `RollbackJob` | Calls the model service rollback endpoint |

---

## Replay test flow

```txt
worker receives replay_test job
    ↓
ReplayTestTool calls model_service /replay-fixture/compare
    ↓
model_service compares current predictions with saved fixture
    ↓
worker passes job only if prediction_mismatches == 0
    ↓
worker sends result to agent
```

Replay tests are useful for warning-level drift because they verify that the serving path and artifacts still behave as expected.

---

## Retrain flow

```txt
worker receives retrain job
    ↓
RetrainTool runs configured command
    ↓
default command: uv run python train.py
    ↓
training script loads original bank-additional-full.csv dataset
    ↓
training creates new model artifacts
    ↓
worker checks training_summary.json
    ↓
worker verifies required artifacts were produced and are fresh
    ↓
worker sends retrain result to agent
```

Required retrain artifacts:

```txt
model_pipeline.joblib
schema.json
runtime_config.json
reference_stats.json
replay_fixture.json
metrics.json
environment.json
model_card.md
training_summary.json
```

The worker does not assume retraining succeeded just because the command exited. It verifies the summary file and artifact freshness before marking the job as completed.

---

## Rollback flow

```txt
worker receives rollback job
    ↓
RollbackTool sends payload to model_service /rollback/production
    ↓
model_service validates and records rollback decision
    ↓
worker sends rollback result to agent
```

In the current local implementation, rollback records the decision for safety and visibility. It does not yet physically switch artifact files.

---

## Retry and DLQ flow

```txt
job fails
    ↓
worker checks retry policy
    ↓
if attempts remain, requeue with incremented attempt count
    ↓
if attempts are exhausted, send job to DLQ
    ↓
notify agent that job is dlq
```

This prevents one broken job from blocking the queue forever.

---

## Idempotency flow

Each job has an `idempotency_key`.

```txt
worker checks if idempotency key already completed
    ↓
if completed, skip duplicate
    ↓
if not completed, acquire lock
    ↓
execute job
    ↓
mark idempotency key as completed after success
```

This protects the project from duplicate retrain, replay, or rollback execution.

---

## Run locally

```bash
cd worker
uv sync
uv run python -m app.main
```

---

## Key environment variables

| Variable | Purpose |
|---|---|
| `WORKER_DATABASE_URL` | Worker/job database connection string |
| `WORKER_REDIS_URL` | Redis connection URL |
| `WORKER_AGENT_URL` | Agent API base URL |
| `WORKER_MODEL_SERVICE_URL` | Model service base URL |
| `WORKER_QUEUE_NAME` | Main Redis queue name |
| `WORKER_QUEUE_PROCESSING_NAME` | Processing queue name |
| `WORKER_QUEUE_DLQ_NAME` | Dead-letter queue name |
| `WORKER_RETRAIN_COMMAND` | Command used to retrain model |
| `WORKER_RETRAIN_WORKING_DIR` | Working directory for retrain command |
| `WORKER_RETRAIN_TIMEOUT_SECONDS` | Maximum retrain time before timeout |

---

## Safe ownership rule

The worker only executes jobs that the agent has queued. It does not decide whether an action is safe. Safety decisions happen in the agent and model service; execution happens here.
