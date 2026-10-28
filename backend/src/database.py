import os

from sqlmodel import SQLModel, create_engine

from models import Discussion, Message, PressReview, User

MODEL_TABLES = (User, Discussion, Message, PressReview)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./newsfoundry.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db():
    SQLModel.metadata.create_all(engine)
