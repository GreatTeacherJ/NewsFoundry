import socket

import pytest
import requests
from pydantic_ai.messages import ModelRequest, ModelResponse
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from lib import callModele
from lib.callModele import (
    MAX_NEWS_ROUNDS,
    Article,
    NeedSearchNews,
    NeedTopNews,
    ParamsSearchNews,
    ParamsTopNews,
    ResModel,
    SearchNewsResponse,
    TopNewsResponse,
    call_modele_chat,
    call_world_new,
    parse_response,
    save_article,
    to_pydantic_history,
)
from models import Discussion, DiscussionSource, Message, Source


# --------------------------------------------------------------------------- #
# Garde-fou : aucun test ne doit pouvoir joindre un vrai service.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("Appel réseau interdit pendant les tests")

    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def discussion(session):
    discussion = Discussion(owner_id=1, title="Test")
    session.add(discussion)
    session.commit()
    session.refresh(discussion)
    return discussion


# --------------------------------------------------------------------------- #
# Faux agent : rejoue une liste de sorties et enregistre les appels.
# --------------------------------------------------------------------------- #
class FakeRun:
    def __init__(self, output, messages):
        self.output = output
        self._messages = messages

    def all_messages(self):
        return self._messages


class FakeAgent:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def run_sync(self, *, user_prompt, message_history=None):
        self.calls.append(
            {"user_prompt": user_prompt, "message_history": list(message_history or [])}
        )
        if not self.outputs:
            raise AssertionError("FakeAgent n'a plus de sortie à rejouer")
        output = self.outputs.pop(0)
        messages = list(message_history or [])
        messages.append(ModelRequest(parts=[]))
        messages.append(ModelResponse(parts=[]))
        return FakeRun(output, messages)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def article_payload(article_id=1, url="https://exemple.fr/article-1"):
    return {
        "id": article_id,
        "title": "Titre de l'article",
        "text": "Contenu de l'article",
        "url": url,
        "publish_date": "2025-09-30",
    }


TOP_NEWS_PAYLOAD = {
    "top_news": [{"news": [article_payload()]}],
    "language": "fr",
    "country": "fr",
}

SEARCH_NEWS_PAYLOAD = {
    "offset": 0,
    "number": 1,
    "available": 1,
    "news": [article_payload()],
}


def top_news_request(**kwargs):
    params = {"source-country": "fr", "language": "fr", **kwargs}
    return NeedTopNews(parametres=ParamsTopNews(**params))


# --------------------------------------------------------------------------- #
# parse_response
# --------------------------------------------------------------------------- #
def test_parse_response_top_news():
    result = parse_response(TOP_NEWS_PAYLOAD)
    assert isinstance(result, TopNewsResponse)
    assert result.top_news[0].news[0].url == "https://exemple.fr/article-1"


def test_parse_response_search_news():
    result = parse_response(SEARCH_NEWS_PAYLOAD)
    assert isinstance(result, SearchNewsResponse)
    assert result.news[0].title == "Titre de l'article"


# --------------------------------------------------------------------------- #
# call_world_new
# --------------------------------------------------------------------------- #
def test_call_world_new_construit_la_requete(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(TOP_NEWS_PAYLOAD)

    monkeypatch.setattr(callModele.requests, "get", fake_get)
    monkeypatch.setenv("API_KEY_WORLD", "test-key")

    request = top_news_request(
        **{"headlines-only": True, "max-news-per-cluster": 3, "date": "2025-09-30"}
    )
    result = call_world_new(request)

    assert isinstance(result, TopNewsResponse)
    assert captured["url"].startswith("https://api.worldnewsapi.com/top-news?")
    assert "source-country=fr" in captured["url"]
    assert "headlines-only=true" in captured["url"]
    assert "max-news-per-cluster=3" in captured["url"]
    assert "date=2025-09-30" in captured["url"]
    assert captured["headers"] == {"x-api-key": "test-key"}
    assert captured["timeout"] == 50


def test_call_world_new_search_news(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResponse(SEARCH_NEWS_PAYLOAD)

    monkeypatch.setattr(callModele.requests, "get", fake_get)

    request = NeedSearchNews(parametres=ParamsSearchNews(text="climat"))
    result = call_world_new(request)

    assert isinstance(result, SearchNewsResponse)
    assert captured["url"].startswith("https://api.worldnewsapi.com/search-news?")
    assert "text=climat" in captured["url"]


def test_call_world_new_propage_les_erreurs_http(monkeypatch):
    monkeypatch.setattr(
        callModele.requests, "get", lambda *args, **kwargs: FakeResponse({}, 500)
    )
    with pytest.raises(requests.HTTPError):
        call_world_new(NeedSearchNews(parametres=ParamsSearchNews(text="climat")))


# --------------------------------------------------------------------------- #
# save_article
# --------------------------------------------------------------------------- #
def test_save_article_cree_puis_reutilise_la_source(session, discussion):
    article = Article(**article_payload())

    save_article([article], session, discussion.id)
    save_article([article], session, discussion.id)

    sources = session.exec(select(Source)).all()
    links = session.exec(select(DiscussionSource)).all()

    assert len(sources) == 1
    assert sources[0].url == article.url
    assert sources[0].content == article.text
    assert len(links) == 1
    assert links[0].source_id == sources[0].id
    assert links[0].discussion_id == discussion.id


# --------------------------------------------------------------------------- #
# to_pydantic_history
# --------------------------------------------------------------------------- #
def test_to_pydantic_history():
    history = to_pydantic_history(
        [
            Message(discussion_id=1, role="user", content="Salut"),
            Message(discussion_id=1, role="assistant", content="Bonjour"),
        ]
    )

    assert isinstance(history[0], ModelRequest)
    assert history[0].parts[0].content == "Salut"
    assert isinstance(history[1], ModelResponse)
    assert history[1].parts[0].content == "Bonjour"


# --------------------------------------------------------------------------- #
# call_modele_chat
# --------------------------------------------------------------------------- #
def test_call_modele_chat_repond_sans_source(session, discussion):
    expected = ResModel(kind="assistant", content="Réponse")

    def fetch(_):
        raise AssertionError("Aucun appel World News ne devait être fait")

    result, sources = call_modele_chat(
        "Bonjour",
        session,
        discussion.id,
        agent=FakeAgent([expected]),
        fetch_world_news=fetch,
    )

    assert result == expected
    assert sources == []


def test_call_modele_chat_ignore_le_message_courant_deja_en_base(session, discussion):
    session.add(Message(discussion_id=discussion.id, role="user", content="Bonjour"))
    session.commit()

    agent = FakeAgent([ResModel(kind="assistant", content="ok")])
    call_modele_chat("Bonjour", session, discussion.id, agent=agent)

    assert agent.calls[0]["message_history"] == []


def test_call_modele_chat_recupere_les_news_puis_conclut(session, discussion):
    request = top_news_request()
    final = ResModel(kind="reviews", content="Synthèse")
    agent = FakeAgent([request, final])
    fetched = []

    def fetch(received):
        fetched.append(received)
        return parse_response(TOP_NEWS_PAYLOAD)

    result, sources = call_modele_chat(
        "Actualités",
        session,
        discussion.id,
        agent=agent,
        fetch_world_news=fetch,
    )

    assert result == final
    assert fetched == [request]
    assert len(sources) == 1
    assert len(session.exec(select(Source)).all()) == 1
    assert len(session.exec(select(DiscussionSource)).all()) == 1

    # Le second appel reçoit l'échange précédent et les données récupérées.
    assert "Résultat de l'appel top-news" in agent.calls[1]["user_prompt"]
    assert "Titre de l'article" in agent.calls[1]["user_prompt"]
    assert len(agent.calls[1]["message_history"]) == 2


def test_call_modele_chat_recupere_une_recherche_puis_conclut(session, discussion):
    request = NeedSearchNews(parametres=ParamsSearchNews(text="climat"))
    final = ResModel(kind="assistant", content="Voici les résultats")
    agent = FakeAgent([request, final])

    result, sources = call_modele_chat(
        "Cherche des news sur le climat",
        session,
        discussion.id,
        agent=agent,
        fetch_world_news=lambda _: parse_response(SEARCH_NEWS_PAYLOAD),
    )

    assert result == final
    assert len(sources) == 1
    assert len(session.exec(select(Source)).all()) == 1


def test_call_modele_chat_limite_les_demandes_de_news(session, discussion):
    request = top_news_request()
    agent = FakeAgent([request] * MAX_NEWS_ROUNDS)
    fetched = []

    def fetch(received):
        fetched.append(received)
        return parse_response(TOP_NEWS_PAYLOAD)

    with pytest.raises(RuntimeError, match="Trop de demandes"):
        call_modele_chat(
            "Actualités",
            session,
            discussion.id,
            agent=agent,
            fetch_world_news=fetch,
        )

    assert len(fetched) == MAX_NEWS_ROUNDS
