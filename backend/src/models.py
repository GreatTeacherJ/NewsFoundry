from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utc_now():
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=320)
    hashed_password: str
    created_at: datetime = Field(default_factory=utc_now)


class Discussion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="Nouvelle discussion", max_length=200)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    discussion_id: int = Field(foreign_key="discussion.id", index=True)
    role: str = Field(max_length=20)
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class PressReview(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    discussion_id: int = Field(foreign_key="discussion.id", index=True)
    title: str = Field(max_length=200)
    content: str
    created_at: datetime = Field(default_factory=utc_now)
