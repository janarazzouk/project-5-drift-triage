# Contracts Flow

The `contracts/` folder contains shared API contract documentation and JSON schemas. These files define the payloads that one service is allowed to send to another service.

Contracts are important because this project has multiple services. The model service, agent, worker, and dashboard should not guess each other's payload shape. The contract makes the communication explicit and safer.

---

## Files in this folder

```txt
contracts/
├── drift_webhook_v1.md
├── drift_webhook_v1.schema.json
├── promotion_request_v1.md
└── promotion_request_v1.schema.json
```

---

## Contract 1: Drift webhook

### Direction

```txt
model_service  →  agent
```

### Purpose

The `model_service` sends this webhook when drift severity changes. For example, if drift moves from `normal` to `warning`, or from `warning` to `critical`, the model service notifies the agent.

### Flow

```txt
model_service runs drift check
    ↓
model_service compares new severity with previous severity
    ↓
if severity changed, build drift webhook payload
    ↓
send POST /webhooks/drift to agent
    ↓
agent validates payload and idempotency key
    ↓
agent opens investigation
```

### Main payload fields

| Field | Meaning |
|---|---|
| `contract_version` | Contract version, currently `v1` |
| `event_type` | Must be `drift.severity_changed` |
| `event_id` | Unique idempotency key for the event |
| `model_name` | Name of the monitored model |
| `model_version` | Version of the monitored model, if available |
| `previous_severity` | Previous drift state |
| `new_severity` | New drift state |
| `overall_score` | Overall drift score |
| `sample_size` | Number of recent records used for drift check |
| `min_required_samples` | Minimum records needed for reliable drift check |
| `drift_report` | Full drift result used by the agent |

### Severity values

```txt
insufficient_data
normal
warning
critical
```

---

## Contract 2: Promotion request

### Direction

```txt
agent  →  model_service
```

### Purpose

The agent sends this request only after a human approves a Production promotion. The agent does not directly promote the model. The model service still owns the final programmatic checklist and can block the promotion if safety checks fail.

### Flow

```txt
human approves promotion in dashboard
    ↓
agent builds promotion request payload
    ↓
agent sends POST /promotion/production to model_service
    ↓
model_service runs promotion checklist
    ↓
if checklist passes, promotion is recorded
    ↓
if checklist fails, promotion is blocked
```

### Main payload fields

| Field | Meaning |
|---|---|
| `contract_version` | Contract version, currently `v1` |
| `request_type` | Must be `promotion.production.requested` |
| `request_id` | Unique idempotency key for the request |
| `investigation_id` | Investigation that caused the request |
| `approval_id` | Human approval record |
| `requested_action` | Must be `promote_to_production` |
| `target_environment` | Must be `production` |
| `model_name` | Model being promoted |
| `model_version` | Candidate model version |
| `human_approval` | Approved-by and approved-at information |
| `reason` | Explanation for why promotion is requested |
| `drift_context` | Optional drift event context |

---

## Why contracts matter in this project

These contracts protect the service boundaries:

```txt
model_service owns detection and model safety checks
agent owns investigation and approval workflow
worker owns slow execution jobs
dashboard owns the human interface
```

When a payload changes, update the schema and the matching service models together. Do not silently change one service without updating the contract.
