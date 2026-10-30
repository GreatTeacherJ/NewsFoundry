import os
import sys
from pathlib import Path

os.environ["JWT_SECRET_KEY"] = "test-secret-with-enough-randomness"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import src.routers.base as base 

import src.main as main

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(engine) as session:
        yield session


main.app.dependency_overrides[base.get_session] = override_get_session
client = TestClient(main.app)


def setup_function():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def register_and_login(email: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": "secure-password"})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"email": email, "password": "secure-password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_registration_login_and_invalid_password():
    token = register_and_login("USER@example.com")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == "user@example.com"
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert client.post("/auth/register", json={"email": "USER@example.com", "password": "secure-password"}).status_code == 409


def test_discussion_messages_and_press_review_lifecycle():
    token = register_and_login("owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/discussions", headers=headers, json={"title": "Actualités"})
    assert response.status_code == 201
    discussion_id = response.json()["id"]

    response = client.post(
        f"/discussions/{discussion_id}/messages",
        headers=headers,
        json={"content": "Résume les actualités"},
    )
    assert response.status_code == 201
    assert [message["role"] for message in response.json()] == ["user", "assistant"]
    assert "aucune IA" in response.json()[1]["content"]
    assert len(client.get(f"/discussions/{discussion_id}/messages", headers=headers).json()) == 2

    response = client.post(f"/discussions/{discussion_id}/press-reviews", headers=headers)
    assert response.status_code == 201
    review_id = response.json()["id"]
    assert "en attente" in response.json()["content"]
    assert client.get("/press-reviews", headers=headers).json()[0]["id"] == review_id
    assert client.delete(f"/press-reviews/{review_id}", headers=headers).status_code == 204


def test_resources_are_isolated_by_owner():
    owner_token = register_and_login("owner@example.com")
    other_token = register_and_login("other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    discussion_id = client.post("/discussions", headers=owner_headers, json={"title": "Privé"}).json()["id"]

    assert client.get("/discussions", headers=other_headers).json() == []
    assert client.get(f"/discussions/{discussion_id}", headers=other_headers).status_code == 404
    assert client.patch(
        f"/discussions/{discussion_id}", headers=other_headers, json={"title": "Volé"}
    ).status_code == 404
    assert client.post(
        f"/discussions/{discussion_id}/messages", headers=other_headers, json={"content": "Intrusion"}
    ).status_code == 404
    assert client.post(f"/discussions/{discussion_id}/press-reviews", headers=other_headers).status_code == 404
    assert client.delete(f"/discussions/{discussion_id}", headers=other_headers).status_code == 404
    assert client.get(f"/discussions/{discussion_id}", headers=owner_headers).json()["title"] == "Privé"


def test_authentication_required_and_bad_token_rejected():
    assert client.get("/discussions").status_code == 401
    assert client.get("/discussions", headers={"Authorization": "Bearer invalid"}).status_code == 401
