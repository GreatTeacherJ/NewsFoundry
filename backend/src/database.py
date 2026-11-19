import os

from sqlmodel import SQLModel, create_engine

from models import Discussion, Message, PressReview, Source, User

MODEL_TABLES = (User, Discussion, Message, PressReview, Source)


def _normalize_database_url(url: str) -> str:
    """SQLAlchemy 2.1 choisit psycopg 3 par défaut ; on force psycopg2."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./newsfoundry.db")
)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db():
    SQLModel.metadata.create_all(engine)
