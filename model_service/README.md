# Model Service Flow

The `model_service/` folder contains the FastAPI service that serves the trained bank marketing model, stores predictions, detects drift, manages model artifact metadata, and blocks unsafe Production promotion through a checklist.

This service owns model behavior. It is the place where prediction, drift analysis, replay comparison, registry state, promotion checks, and rollback recording happen.

---

## Folder structure

```txt
model_service/
├── app/
│   ├── core/          # Settings, database setup, dependency injection
│   ├── models/        # SQLAlchemy database tables
│   ├── routers/       # FastAPI endpoints
│   ├── schemas/       # Pydantic request/response models
│   └── services/      # Prediction, drift, registry, promotion, rollback logic
├── artifacts/         # Current model artifacts used by the API
├── training/          # Training pipeline modules
├── train.py           # Entrypoint for retraining/training
├── Dockerfile
└── pyproject.toml
```

---

## Main responsibility

The model service answers this question:

```txt
Is the deployed model still safe and reliable enough to use?
```

It does this by:

1. Loading the saved model pipeline and runtime config.
2. Serving predictions through `/predict`.
3. Saving prediction records for later drift checks.
4. Comparing recent data against training reference statistics.
5. Sending a drift webhook to the agent when severity changes.
6. Running replay checks to prove the serving path still behaves correctly.
7. Running a promotion checklist before Production promotion is allowed.

---

## Startup flow

When the FastAPI app starts, `app/main.py` calls `initialize_resources()`.

```txt
start FastAPI
    ↓
load settings from .env using MODEL_SERVICE_ prefix
    ↓
initialize database tables
    ↓
load model_pipeline.joblib
    ↓
load schema.json and runtime_config.json
    ↓
load reference_stats.json
    ↓
save or update registry state in database
    ↓
save or update reference statistics in database
```

The service uses dependency injection in `app/core/dependencies.py` so routers do not manually create predictors, services, or database sessions.

---

## Prediction flow

Endpoint:

```txt
POST /predict
```

Flow:

```txt
client sends request_id + features
    ↓
PredictionRequest validates payload shape
    ↓
Predictor checks required columns from schema.json
    ↓
Predictor handles pdays special rule
    ↓
model pipeline returns positive-class probability
    ↓
threshold from runtime_config.json converts probability to class
    ↓
prediction is saved to database
    ↓
API returns probability, predicted_class, threshold, model_version
```

The same preprocessing rules used during training are preserved through the saved scikit-learn pipeline.

---

## Drift flow

Endpoint:

```txt
GET /drift
```

Flow:

```txt
load recent prediction records from database
    ↓
if records < drift_min_samples, return insufficient_data
    ↓
compare recent feature distributions with reference_stats.json
    ↓
calculate numeric/categorical/output drift scores
    ↓
assign severity: normal, warning, or critical
    ↓
save drift check result
    ↓
if severity changed, send webhook to agent
```

The webhook goes to the URL configured by:

```txt
MODEL_SERVICE_AGENT_DRIFT_WEBHOOK_URL
```

Example local value:

```txt
MODEL_SERVICE_AGENT_DRIFT_WEBHOOK_URL=http://127.0.0.1:8010/webhooks/drift
```

---

## Training and retraining flow

Entrypoint:

```txt
uv run python train.py
```

The training pipeline uses the original bank marketing dataset, not the old model artifact.

Flow:

```txt
load bank-additional-full.csv
    ↓
map target y: yes → 1, no → 0
    ↓
drop duration to avoid label leakage
    ↓
handle pdays == 999 by creating pdays_was_999 and replacing pdays with -1
    ↓
keep unknown categories as real category values
    ↓
split data into 60% train, 20% validation, 20% test
    ↓
build preprocessing + LogisticRegression pipeline
    ↓
choose highest threshold where validation recall meets the minimum recall target
    ↓
evaluate train, validation, and test metrics
    ↓
save artifacts
    ↓
register model in MLflow
```

Important generated artifacts:

| Artifact | Purpose |
|---|---|
| `model_pipeline.joblib` | Trained preprocessing + model pipeline |
| `schema.json` | Required model input columns and feature metadata |
| `runtime_config.json` | Runtime threshold, model version, MLflow metadata |
| `reference_stats.json` | Training reference distributions for drift detection |
| `replay_fixture.json` | Saved samples and expected outputs for replay testing |
| `metrics.json` | Train/validation/test metrics |
| `environment.json` | Runtime/training environment metadata |
| `model_card.md` | Human-readable model summary |
| `training_summary.json` | Worker-verifiable retraining result summary |

---

## Replay flow

Endpoints:

```txt
GET /replay-fixture
GET /replay-fixture/compare
```

Flow:

```txt
load replay_fixture.json
    ↓
run current model on saved fixture rows
    ↓
compare current probability and prediction with expected values
    ↓
return mismatch count and max probability difference
```

The worker uses this during the `replay_test` job. A clean replay test means the current serving path still matches the expected artifact behavior.

---

## Promotion checklist flow

Endpoints:

```txt
GET /promotion/checklist
POST /promotion/production
```

The model service blocks promotion unless the checklist passes.

The checklist verifies things like:

- model is loaded
- required artifacts exist
- metrics meet configured minimums
- replay comparison has no unexpected mismatches
- latest drift severity is allowed for promotion
- requested model version matches the loaded candidate model

Flow:

```txt
agent sends promotion request after human approval
    ↓
model_service validates request
    ↓
model_service runs checklist
    ↓
if checklist fails, return promoted=false
    ↓
if checklist passes, record promotion decision
```

---

## Rollback flow

Endpoint:

```txt
POST /rollback/production
```

This local implementation records a rollback decision for the currently loaded model version. It does not physically switch model artifacts yet. The goal is to keep the workflow safe and visible while preserving the old artifacts for comparison and rollback planning.

---

## Main endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health and model-loaded status |
| `POST` | `/predict` | Run prediction and save record |
| `GET` | `/registry` | Current model metadata and artifact paths |
| `GET` | `/drift` | Drift analysis and webhook trigger if severity changed |
| `GET` | `/replay-fixture` | Return replay fixture |
| `GET` | `/replay-fixture/compare` | Compare current serving output with fixture |
| `GET` | `/promotion/checklist` | Run Production safety checklist |
| `POST` | `/promotion/production` | Request Production promotion after approval |
| `POST` | `/rollback/production` | Record rollback decision |

---

## Run locally

```bash
cd model_service
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Train or retrain:

```bash
cd model_service
uv run python train.py
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

---

## Key environment variables

| Variable | Purpose |
|---|---|
| `MODEL_SERVICE_DATABASE_URL` | Database connection string |
| `MODEL_SERVICE_ARTIFACT_DIR` | Path to model artifacts |
| `MODEL_SERVICE_AGENT_DRIFT_WEBHOOK_URL` | Agent drift webhook URL |
| `MODEL_SERVICE_DRIFT_MIN_SAMPLES` | Minimum samples before reliable drift decision |
| `MODEL_SERVICE_DRIFT_WARNING_THRESHOLD` | Warning drift threshold |
| `MODEL_SERVICE_DRIFT_CRITICAL_THRESHOLD` | Critical drift threshold |
| `MODEL_SERVICE_PROMOTION_MIN_RECALL` | Minimum recall for promotion checklist |
| `MODEL_SERVICE_PROMOTION_ALLOWED_DRIFT_SEVERITIES` | Drift severities allowed during promotion |

---

## Safe ownership rule

The model service owns model safety checks. Even if the agent or dashboard requests promotion, the model service can still block it if the checklist fails.
