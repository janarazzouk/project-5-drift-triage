# Agent Flow

The `agent/` folder contains the FastAPI service that receives drift webhooks, opens investigations, runs the decision workflow, creates human approval requests, and enqueues background jobs in Redis.

The agent does not directly change Production. Its job is to investigate, explain, and coordinate safe actions.

---

## Folder structure

```txt
agent/
├── app/
│   ├── agents/         # LangGraph-style supervisor, routing, nodes, prompts
│   ├── api/            # FastAPI routers for webhooks, investigations, approvals, queue
│   ├── contracts/      # Pydantic versions of shared contracts
│   ├── core/           # Settings, database, Redis, dependencies, logging, errors
│   ├── models/         # SQLAlchemy tables
│   ├── repositories/   # Database access layer
│   ├── schemas/        # API response/request models
│   └── services/       # Webhook, investigation, approval, queue services
├── Dockerfile
└── pyproject.toml
```

---

## Main responsibility

The agent answers this question:

```txt
Drift happened. What should the system do next, safely?
```

It does this by:

1. Receiving drift events from the model service.
2. Creating an investigation.
3. Running triage and action decision logic.
4. Asking for human approval before risky Production actions.
5. Creating Redis jobs for slow actions like replay tests and retraining.
6. Recording every state transition for the dashboard.

---

## Incoming drift webhook flow

Endpoint:

```txt
POST /webhooks/drift
```

Flow:

```txt
model_service sends drift webhook
    ↓
agent validates X-Contract-Version and X-Idempotency-Key
    ↓
agent checks if event_id already exists
    ↓
if duplicate, return duplicate=true and do not open another case
    ↓
store drift event
    ↓
create investigation
    ↓
run investigation graph
    ↓
apply final decision
```

The webhook is idempotent. If the same `event_id` arrives again, the agent does not create a duplicate investigation.

---

## Investigation graph flow

The agent workflow is implemented through graph nodes in `app/agents/`.

```txt
START
  ↓
supervisor
  ↓
triage
  ↓
supervisor
  ↓
action
  ↓
supervisor
  ↓
approval
  ↓
supervisor
  ↓
comms
  ↓
supervisor
  ↓
completion
  ↓
END
```

### What each node does

| Node | Role |
|---|---|
| `supervisor` | Decides which node should run next |
| `triage` | Converts drift severity into risk level and primary issue |
| `action` | Chooses recommended action such as monitor, replay, retrain, or rollback |
| `approval` | Marks whether human approval is required |
| `comms` | Builds a clear investigation summary |
| `completion` | Sets final state such as resolved, waiting for job, or waiting for approval |

---

## Action decision logic

| Severity | Agent decision | Result |
|---|---|---|
| `insufficient_data` | `monitor` | Resolve/continue monitoring |
| `normal` | `monitor` or `resolve` | No queue job and no approval |
| `warning` | `replay_test` | Queue a replay test job |
| `critical` feature drift | `retrain` | Wait for human approval, then queue retrain |
| `critical` output drift or critical after warning | `rollback_production` | Wait for human approval, then queue rollback |

This keeps the system safe because critical actions do not execute automatically.

---

## Approval flow

Endpoints:

```txt
GET  /approvals/pending
POST /approvals/{approval_id}/approve
POST /approvals/{approval_id}/reject
```

Flow:

```txt
agent decides production_action_required=true
    ↓
agent creates approval record
    ↓
dashboard shows pending approval
    ↓
human approves or rejects
    ↓
if rejected, investigation is not executed
    ↓
if approved, agent performs the approved side effect
```

Approved side effects:

| Requested action | What happens after approval |
|---|---|
| `retrain` | Agent queues a `retrain` job in Redis |
| `rollback_production` | Agent queues a rollback job for the worker |
| `promote_to_production` | Agent sends a promotion request to model service |

---

## Queue flow

The agent owns job creation. The worker owns job execution.

```txt
agent creates job record in database
    ↓
agent pushes job envelope to Redis
    ↓
worker consumes job
    ↓
worker executes tool
    ↓
worker posts result to /queue/jobs/result
    ↓
agent updates job and investigation state
```

The agent creates an idempotency key for jobs so the same action is not queued again accidentally.

---

## Main endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check database and Redis connectivity |
| `POST` | `/webhooks/drift` | Receive drift webhook from model service |
| `GET` | `/investigations` | List investigations |
| `GET` | `/investigations/open` | List open investigations |
| `GET` | `/investigations/{id}` | Read one investigation |
| `GET` | `/investigations/{id}/summary` | Read investigation with messages, jobs, approvals |
| `GET` | `/approvals` | List approvals |
| `GET` | `/approvals/pending` | List pending approvals |
| `POST` | `/approvals/{id}/approve` | Approve an action |
| `POST` | `/approvals/{id}/reject` | Reject an action |
| `GET` | `/queue/status` | Queue counts and recent jobs |
| `GET` | `/queue/jobs` | List tracked jobs |
| `GET` | `/queue/jobs/{job_id}` | Read one job |
| `POST` | `/queue/jobs/result` | Worker callback for job result |

---

## Run locally

```bash
cd agent
uv sync
uv run uvicorn app.main:app --reload --port 8010
```

Health check:

```bash
curl http://127.0.0.1:8010/health
```

---

## Key environment variables

| Variable | Purpose |
|---|---|
| `AGENT_DATABASE_URL` | Agent database connection string |
| `AGENT_LANGGRAPH_CHECKPOINT_DB_URI` | LangGraph checkpoint database URI |
| `AGENT_REDIS_URL` | Redis connection URL |
| `AGENT_MODEL_SERVICE_URL` | Base URL for model service |
| `AGENT_QUEUE_NAME` | Redis queue name |
| `AGENT_QUEUE_PROCESSING_NAME` | Redis processing queue |
| `AGENT_QUEUE_DLQ_NAME` | Redis dead-letter queue |
| `AGENT_JOB_MAX_ATTEMPTS` | Maximum job attempts before DLQ |

---

## Safe ownership rule

The agent can recommend actions, but it should not silently change Production. It either asks the dashboard for human approval or sends a request to the model service, where final safety checks are still enforced.
