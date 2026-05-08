# Dashboard Flow

The `dashboard/` folder contains the Streamlit dashboard used by the human operator. It is the visual control layer for monitoring drift, viewing investigations, approving or rejecting actions, and watching queue/job results.

The dashboard does not own the business logic. It reads from the `agent` and `model_service` APIs, then sends approval decisions back to the agent.

---

## Folder structure

```txt
dashboard/
├── dashboard.py          # Streamlit entrypoint and navigation
├── ui/
│   ├── api.py            # API client for agent and model_service
│   ├── config.py         # Dashboard environment config
│   ├── components.py     # Reusable UI cards, pills, error blocks
│   ├── styles.py         # Global CSS styling
│   └── pages/            # Dashboard pages
├── Dockerfile
└── pyproject.toml
```

---

## Main responsibility

The dashboard answers this question:

```txt
What is happening with the model, and what does the human need to approve?
```

It does this by showing:

1. Service health.
2. Current drift status.
3. Investigations opened by the agent.
4. Pending human approvals.
5. Queue and worker job results.
6. Registry and promotion checklist state.
7. Demo controls for presentation/testing.

---

## Dashboard navigation flow

`dashboard.py` builds the sidebar and routes to one page at a time:

```txt
Overview
Drift Monitor
Investigations
Human Approvals
Queue & Jobs
Registry & Promotion
Demo Controls
```

Each page receives the same `ApiClient`, so API access stays centralized in `ui/api.py`.

---

## API client flow

The dashboard reads two base URLs from environment variables:

```txt
AGENT_API_URL
MODEL_SERVICE_API_URL
```

Flow:

```txt
load dashboard config
    ↓
create ApiClient
    ↓
page calls ApiClient method
    ↓
ApiClient sends request to agent or model_service
    ↓
page renders cards, tables, or forms
```

---

## Page flows

### Overview

Shows a quick summary of health, pending approvals, queue status, and recent investigations.

```txt
agent /health
model_service /health
agent /queue/status
agent /approvals/pending
agent /investigations
```

### Drift Monitor

Shows the latest drift status and important drift features.

```txt
model_service /drift
fallback: recent investigation drift_report from agent
```

### Investigations

Lists investigations and lets the user inspect one investigation in detail.

```txt
agent /investigations
agent /investigations/{id}/summary
```

The detail view shows state, summary, jobs, approvals, candidate model information, and promotion result when available.

### Human Approvals

Shows pending approvals and lets the human approve or reject.

```txt
agent /approvals/pending
agent /approvals
POST agent /approvals/{approval_id}/approve
POST agent /approvals/{approval_id}/reject
```

This is the most important safety page because it prevents serious Production actions from happening without a human decision.

### Queue & Jobs

Shows Redis queue counts and tracked job records.

```txt
agent /queue/status
```

This page is useful for explaining whether a replay, retrain, or rollback job is queued, running, completed, retrying, or sent to DLQ.

### Registry & Promotion

Shows the loaded model metadata and the Production promotion checklist.

```txt
model_service /registry
model_service /promotion/checklist
```

### Demo Controls

Sends synthetic drift webhooks directly to the agent. This is for local demo and presentation only.

```txt
POST agent /webhooks/drift
```

Demo controls help show the full flow without waiting for real drift to naturally happen.

---

## Human approval flow

```txt
dashboard loads pending approvals
    ↓
human reads action, target, reason, model version
    ↓
human approves or rejects
    ↓
dashboard posts decision to agent
    ↓
agent queues job or calls model service if approved
    ↓
agent records rejection if rejected
    ↓
dashboard refreshes state
```

---

## Run locally

```bash
cd dashboard
uv sync
uv run streamlit run dashboard.py --server.port 8501
```

Then open:

```txt
http://localhost:8501
```

---

## Key environment variables

| Variable | Purpose |
|---|---|
| `AGENT_API_URL` | Base URL for the agent API |
| `MODEL_SERVICE_API_URL` | Base URL for the model service API |
| `DASHBOARD_REQUEST_TIMEOUT_SECONDS` | Request timeout for dashboard API calls |

Example local values:

```txt
AGENT_API_URL=http://127.0.0.1:8010
MODEL_SERVICE_API_URL=http://127.0.0.1:8000
DASHBOARD_REQUEST_TIMEOUT_SECONDS=8
```

---

## Safe ownership rule

The dashboard is where the human makes the final approval decision. It should show clear information and avoid hiding risky actions behind automation.
