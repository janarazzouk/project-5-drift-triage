from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.base import Base

# These imports are needed so SQLAlchemy registers all tables before create_all().
from app.models.agent_message import AgentMessage  # noqa: F401
from app.models.approval import Approval  # noqa: F401
from app.models.drift_event import DriftEvent  # noqa: F401
from app.models.investigation import Investigation  # noqa: F401
from app.models.job_record import JobRecord  # noqa: F401


def build_engine(settings: Settings):
    connect_args = {}

    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def build_session_factory(settings: Settings) -> sessionmaker:
    engine = build_engine(settings)

    return sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )


def init_db(settings: Settings) -> None:
    engine = build_engine(settings)
    Base.metadata.create_all(bind=engine)


def check_db_connection(settings: Settings) -> bool:
    engine = build_engine(settings)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True


def get_db_session(session_factory: sessionmaker) -> Generator[Session, None, None]:
    db = session_factory()

    try:
        yield db
    finally:
        db.close()