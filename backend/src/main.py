import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from pydantic import Field as SchemaField
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from database import engine, init_db
from models import Discussion, Message, PressReview, User, utc_now

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "480"))
JWT_ALGORITHM = "HS256"
DEMO_ASSISTANT_RESPONSE = "Réponse de démonstration : aucune IA n’est connectée pour le moment."
DEMO_PRESS_REVIEW = "Revue de presse en attente : aucune source ni IA n’est configurée."

app = FastAPI(title="NewsFoundry API", version="0.1.0")
origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
# Schéma « HTTP bearer » : Swagger affiche un simple champ où coller le jeton
# obtenu via POST /auth/login (le préfixe « Bearer » est ajouté automatiquement).
# auto_error=False permet de renvoyer 401 (et non 403) quand l'en-tête est absent.
bearer_scheme = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: EmailStr
    password: str = SchemaField(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode()) > 72:
            raise ValueError("Le mot de passe ne peut pas dépasser 72 octets.")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr


class DiscussionCreate(BaseModel):
    title: str = SchemaField(default="Nouvelle discussion", min_length=1, max_length=200)


class DiscussionUpdate(BaseModel):
    title: str = SchemaField(min_length=1, max_length=200)


class DiscussionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = SchemaField(min_length=1, max_length=20000)


class MessageUpdate(BaseModel):
    content: str = SchemaField(min_length=1, max_length=20000)


class PressReviewUpdate(BaseModel):
    title: str = SchemaField(min_length=1, max_length=200)
    content: str = SchemaField(min_length=1, max_length=20000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discussion_id: int
    role: str
    content: str
    created_at: datetime


class PressReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discussion_id: int
    title: str
    content: str
    created_at: datetime


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="L’authentification n’est pas configurée.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise jwt.InvalidTokenError
        user = session.get(User, int(user_id))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def create_access_token(user: User) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=JWT_ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "exp": expires_at}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_owned_discussion(session: Session, discussion_id: int, owner_id: int) -> Discussion:
    discussion = session.exec(
        select(Discussion).where(Discussion.id == discussion_id, Discussion.owner_id == owner_id)
    ).first()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion introuvable.")
    return discussion


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Cette ressource existe déjà."})


@app.get("/")
def health_check():
    return {"message": "NewsFoundry API opérationnelle"}


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, session: SessionDep):
    email = payload.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée.")
    user = User(email=email, hashed_password=bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode())
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée.") from None
    session.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: Credentials, session: SessionDep):
    user = session.exec(select(User).where(User.email == payload.email.lower())).first()
    password_matches = user is not None and bcrypt.checkpw(payload.password.encode(), user.hashed_password.encode())
    if not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse e-mail ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="L’authentification n’est pas configurée.")
    return TokenResponse(access_token=create_access_token(user))


@app.get("/auth/me", response_model=UserResponse)
def read_me(user: CurrentUser):
    return user


@app.get("/discussions", response_model=list[DiscussionResponse])
def list_discussions(user: CurrentUser, session: SessionDep):
    return session.exec(
        select(Discussion).where(Discussion.owner_id == user.id).order_by(Discussion.updated_at.desc())
    ).all()


@app.post("/discussions", response_model=DiscussionResponse, status_code=status.HTTP_201_CREATED)
def create_discussion(payload: DiscussionCreate, user: CurrentUser, session: SessionDep):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Le titre ne peut pas être vide.")
    discussion = Discussion(owner_id=user.id, title=title)
    session.add(discussion)
    session.commit()
    session.refresh(discussion)
    return discussion


@app.get("/discussions/{discussion_id}", response_model=DiscussionResponse)
def read_discussion(discussion_id: int, user: CurrentUser, session: SessionDep):
    return get_owned_discussion(session, discussion_id, user.id)


@app.patch("/discussions/{discussion_id}", response_model=DiscussionResponse)
def update_discussion(discussion_id: int, payload: DiscussionUpdate, user: CurrentUser, session: SessionDep):
    discussion = get_owned_discussion(session, discussion_id, user.id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Le titre ne peut pas être vide.")
    discussion.title = title
    discussion.updated_at = utc_now()
    session.add(discussion)
    session.commit()
    session.refresh(discussion)
    return discussion


@app.delete("/discussions/{discussion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discussion(discussion_id: int, user: CurrentUser, session: SessionDep):
    discussion = get_owned_discussion(session, discussion_id, user.id)
    messages = session.exec(select(Message).where(Message.discussion_id == discussion.id)).all()
    reviews = session.exec(select(PressReview).where(PressReview.discussion_id == discussion.id)).all()
    for item in [*messages, *reviews]:
        session.delete(item)
    session.delete(discussion)
    session.commit()


@app.get("/discussions/{discussion_id}/messages", response_model=list[MessageResponse])
def list_messages(discussion_id: int, user: CurrentUser, session: SessionDep):
    get_owned_discussion(session, discussion_id, user.id)
    return session.exec(
        select(Message).where(Message.discussion_id == discussion_id).order_by(Message.created_at, Message.id)
    ).all()


@app.post("/discussions/{discussion_id}/messages", response_model=list[MessageResponse], status_code=status.HTTP_201_CREATED)
def create_message(discussion_id: int, payload: MessageCreate, user: CurrentUser, session: SessionDep):
    discussion = get_owned_discussion(session, discussion_id, user.id)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Le message ne peut pas être vide.")
    message = Message(discussion_id=discussion.id, role="user", content=content)
    assistant = Message(discussion_id=discussion.id, role="assistant", content=DEMO_ASSISTANT_RESPONSE)
    discussion.updated_at = utc_now()
    session.add(message)
    session.add(assistant)
    session.add(discussion)
    session.commit()
    session.refresh(message)
    session.refresh(assistant)
    return [message, assistant]


@app.patch("/discussions/{discussion_id}/messages/{message_id}", response_model=MessageResponse)
def update_message(
    discussion_id: int,
    message_id: int,
    payload: MessageUpdate,
    user: CurrentUser,
    session: SessionDep,
):
    get_owned_discussion(session, discussion_id, user.id)
    message = session.exec(
        select(Message).where(Message.id == message_id, Message.discussion_id == discussion_id)
    ).first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message introuvable.")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Le message ne peut pas être vide.")
    message.content = content
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@app.delete("/discussions/{discussion_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(discussion_id: int, message_id: int, user: CurrentUser, session: SessionDep):
    get_owned_discussion(session, discussion_id, user.id)
    message = session.exec(
        select(Message).where(Message.id == message_id, Message.discussion_id == discussion_id)
    ).first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message introuvable.")
    session.delete(message)
    session.commit()


@app.get("/press-reviews", response_model=list[PressReviewResponse])
def list_press_reviews(user: CurrentUser, session: SessionDep):
    return session.exec(
        select(PressReview).where(PressReview.owner_id == user.id).order_by(PressReview.created_at.desc())
    ).all()


@app.post(
    "/discussions/{discussion_id}/press-reviews",
    response_model=PressReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_press_review(discussion_id: int, user: CurrentUser, session: SessionDep):
    discussion = get_owned_discussion(session, discussion_id, user.id)
    review = PressReview(
        owner_id=user.id,
        discussion_id=discussion.id,
        title=f"Revue de presse — {discussion.title}",
        content=DEMO_PRESS_REVIEW,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


@app.get("/press-reviews/{review_id}", response_model=PressReviewResponse)
def read_press_review(review_id: int, user: CurrentUser, session: SessionDep):
    review = session.exec(
        select(PressReview).where(PressReview.id == review_id, PressReview.owner_id == user.id)
    ).first()
    if review is None:
        raise HTTPException(status_code=404, detail="Revue de presse introuvable.")
    return review


@app.patch("/press-reviews/{review_id}", response_model=PressReviewResponse)
def update_press_review(
    review_id: int,
    payload: PressReviewUpdate,
    user: CurrentUser,
    session: SessionDep,
):
    review = session.exec(
        select(PressReview).where(PressReview.id == review_id, PressReview.owner_id == user.id)
    ).first()
    if review is None:
        raise HTTPException(status_code=404, detail="Revue de presse introuvable.")
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(status_code=422, detail="Le titre et le contenu ne peuvent pas être vides.")
    review.title = title
    review.content = content
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


@app.delete("/press-reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_press_review(review_id: int, user: CurrentUser, session: SessionDep):
    review = session.exec(
        select(PressReview).where(PressReview.id == review_id, PressReview.owner_id == user.id)
    ).first()
    if review is None:
        raise HTTPException(status_code=404, detail="Revue de presse introuvable.")
    session.delete(review)
    session.commit()


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
