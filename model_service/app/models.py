from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class PredictionRecord(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    request_id = Column(String, index=True, nullable=False)

    features_json = Column(JSON, nullable=False)

    probability = Column(Float, nullable=False)
    predicted_class = Column(Integer, nullable=False)
    threshold = Column(Float, nullable=False)

    model_version = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RegistryState(Base):
    __tablename__ = "registry_state"

    id = Column(Integer, primary_key=True, index=True)

    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=True)
    model_stage = Column(String, nullable=True)

    artifact_uri = Column(Text, nullable=True)

    selected_threshold = Column(Float, nullable=False)

    metrics_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ReferenceStatistics(Base):
    __tablename__ = "reference_statistics"

    id = Column(Integer, primary_key=True, index=True)

    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=True)

    stats_json = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class DriftCheck(Base):
    __tablename__ = "drift_checks"

    id = Column(Integer, primary_key=True, index=True)

    sample_size = Column(Integer, nullable=False)

    overall_score = Column(Float, nullable=False)
    severity = Column(String, nullable=False)

    details_json = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)