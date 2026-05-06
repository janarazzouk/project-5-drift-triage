import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_ENV = ROOT_DIR / ".env"
MODEL_SERVICE_DIR = ROOT_DIR / "model_service"

sys.path.insert(0, str(MODEL_SERVICE_DIR))


def load_root_env() -> None:
    """
    Loads the root .env file manually.

    Your .env is here:
    project-5-drift-triage/.env

    Not here:
    model_service/.env
    """
    if not ROOT_ENV.exists():
        raise FileNotFoundError(
            f"Root .env file was not found at: {ROOT_ENV}"
        )

    for line in ROOT_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ[key] = value


load_root_env()


from app.config import get_settings
from app.database import build_engine, build_session_factory, init_db, save_prediction

try:
    from app.models import Base, PredictionRecord
except ImportError:
    from app.database import Base, PredictionRecord


@pytest.fixture()
def settings():
    get_settings.cache_clear()
    return get_settings()


def test_database_url_is_postgresql(settings):
    assert settings.database_url.startswith("postgresql"), (
        "MODEL_SERVICE_DATABASE_URL is not using PostgreSQL. "
        "Check your root .env file and make sure it contains something like:\n"
        "MODEL_SERVICE_DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/drift_triage"
    )


def test_database_connection_works(settings):
    engine = build_engine(settings)

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar()

    assert result == 1


def test_init_db_creates_declared_tables(settings):
    init_db(settings)

    engine = build_engine(settings)
    inspector = inspect(engine)

    existing_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())

    assert expected_tables, (
        "No SQLAlchemy tables were found in Base.metadata. "
        "Make sure your table classes inherit from Base."
    )

    missing_tables = expected_tables - existing_tables

    assert not missing_tables, (
        f"These tables were declared in SQLAlchemy but were not created in PostgreSQL: {missing_tables}. "
        f"Existing tables: {existing_tables}"
    )


def test_prediction_can_be_saved_and_read(settings):
    init_db(settings)

    session_factory = build_session_factory(settings)
    db = session_factory()

    request_id = "database-test-request"

    try:
        record = save_prediction(
            db,
            request_id=request_id,
            features={
                "age": 35,
                "job": "admin.",
                "marital": "married",
                "education": "university.degree",
                "default": "no",
                "housing": "yes",
                "loan": "no",
                "contact": "cellular",
                "month": "may",
                "day_of_week": "mon",
                "campaign": 2,
                "pdays": -1,
                "previous": 0,
                "poutcome": "nonexistent",
                "emp.var.rate": 1.1,
                "cons.price.idx": 93.994,
                "cons.conf.idx": -36.4,
                "euribor3m": 4.857,
                "nr.employed": 5191.0,
                "pdays_was_999": 1,
            },
            probability=0.73,
            predicted_class=1,
            threshold=0.5,
            model_version="test-version",
        )

        saved = (
            db.query(PredictionRecord)
            .filter(PredictionRecord.request_id == request_id)
            .order_by(PredictionRecord.id.desc())
            .first()
        )

        assert saved is not None
        assert saved.id == record.id
        assert saved.probability == 0.73
        assert saved.predicted_class == 1
        assert saved.threshold == 0.5
        assert saved.model_version == "test-version"

    finally:
        db.close()