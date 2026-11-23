import json
import logging
import os
from datetime import date as dt
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import mlflow
import requests
from dotenv import load_dotenv  # uv add python-dotenv
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlmodel import Session, select

from lib.prompt_systeme import PROMPT_SYSTEME_BASE, instruction_date_du_jour
from models import DiscussionSource, Message, Source

# Charge le .env AVANT toute lecture de variable d'environnement (dont MLflow)
load_dotenv()

logger = logging.getLogger(__name__)

# Le tracing MLflow est optionnel : sans serveur joignable, on bascule sur un
# stockage SQLite local pour que l'API démarre toujours (set_experiment bloque
# sinon plusieurs minutes en essayant de joindre le serveur).
MLFLOW_SQLITE_URI = f"sqlite:///{Path(__file__).resolve().parents[2] / 'mlflow.db'}"


def _configure_mlflow() -> None:
    #Désactive mlFlow en production
    if os.getenv("MLFLOW_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        logger.info("Tracing MLflow désactivé (MLFLOW_ENABLED=false).")
        return
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI") or MLFLOW_SQLITE_URI
    if tracking_uri.startswith(("http://", "https://")):
        try:
            requests.get(f"{tracking_uri.rstrip('/')}/health", timeout=1).raise_for_status()
        except requests.RequestException:
            logger.warning(
                "Serveur MLflow injoignable (%s) : tracing enregistré en local (%s).",
                tracking_uri,
                MLFLOW_SQLITE_URI,
            )
            tracking_uri = MLFLOW_SQLITE_URI
    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "weather-agent"))
        mlflow.pydantic_ai.autolog()  # branche la collecte des traces
    except Exception:
        # Le tracing ne doit jamais empêcher le serveur de démarrer.
        logger.warning("Initialisation MLflow impossible, tracing désactivé.", exc_info=True)


_configure_mlflow()


class ParamsTopNews(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_country: str = Field(alias="source-country", pattern=r"^[a-z]{2}$")
    language: str = Field(pattern=r"^[a-z]{2}$")
    date: dt | None = None
    headlines_only: bool | None = Field(default=None, alias="headlines-only")
    max_news_per_cluster: int | None = Field(
        default=None, alias="max-news-per-cluster", ge=1, le=10
    )

class ParamsSearchNews(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str | None = None
    text_match_indexes: str | None = Field(default=None, alias="text-match-indexes")
    source_country: str | None = Field(default=None, alias="source-country")
    language: str | None = None
    earliest_publish_date: dt | None = Field(default=None, alias="earliest-publish-date")
    latest_publish_date: dt | None = Field(default=None, alias="latest-publish-date")
    categories: str | None = None


class ResModel(BaseModel):
    kind: Literal["reviews", "assistant"]
    content: str


class NeedTopNews(BaseModel):
    kind: Literal["top-news"] = "top-news"
    parametres: ParamsTopNews


class NeedSearchNews(BaseModel):
    kind: Literal["search-news"] = "search-news"
    parametres: ParamsSearchNews


class Article(BaseModel):
    id: int
    title: str
    text: str
    url: str
    publish_date: str
    image: str | None = None
    video: str | None = None
    summary: str | None = None
    author: str | None = None
    authors: list[str] = Field(default_factory=list)
    category: str | None = None
    language: str | None = None
    source_country: str | None = None
    sentiment: float | None = None


class NewsCluster(BaseModel):
    news: list[Article]


class TopNewsResponse(BaseModel):
    top_news: list[NewsCluster]
    language: str
    country: str


class SearchNewsResponse(BaseModel):
    offset: int
    number: int
    available: int
    news: list[Article]


NewsApiResponse = TopNewsResponse | SearchNewsResponse
_adapter = TypeAdapter(NewsApiResponse)


def parse_response(raw: dict) -> NewsApiResponse:
    # Pydantic essaie chaque type de l'union dans l'ordre (mode "smart" par défaut)
    # et retourne le premier qui valide. Lève ValidationError si aucun ne match.
    return _adapter.validate_python(raw)


MAX_NEWS_ROUNDS = 3

review = """**REVUE DE PRESSE POLITIQUE - 30 Septembre 2025**

**Synthèse hebdomadaire des principales actualités politiques :**

• **Réforme économique** : Le gouvernement a présenté son plan de relance économique avec des mesures ciblées sur l'emploi et l'innovation. Les réactions sont mitigées entre opposition et majorité.

• **Relations internationales** : Préparation du sommet européen avec focus sur les questions énergétiques et la coopération en matière de défense.

• **Politique intérieure** : Débats parlementaires sur la réforme du système de santé, avec des amendements proposés par différents groupes politiques.

**Perspectives** : Les prochaines semaines seront cruciales pour l'adoption des mesures proposées et leur impact sur l'opinion publique."""

# "test" = faux modèle (aucune clé requise), sinon un vrai modèle
MODEL_NAME = os.getenv("AI_MODEL", "test")


def build_model(custom_output_args: dict) -> TestModel | OpenAIChatModel:
    """Construit le modèle à utiliser, sans clé ni réseau quand AI_MODEL=test."""
    if MODEL_NAME == "test":
        return TestModel(custom_output_args=custom_output_args)
    return OpenAIChatModel(
        "mammouth-recommended",
        provider=OpenAIProvider(
            base_url="https://api.mammouth.ai/v1",
            api_key=os.getenv("MAMMOUTH_KEY"),
        ),
    )


chat_agent = Agent(
    build_model({"kind": "reviews", "content": review}),
    # `instructions` (et non `system_prompt`) : PydanticAI ne rejoue pas le system_prompt
    # quand un `message_history` est fourni, le modèle perdrait alors son rôle dès le
    # 2e message d'une discussion. Les instructions, elles, sont envoyées à chaque appel.
    instructions=PROMPT_SYSTEME_BASE,
    output_type=ResModel | NeedTopNews | NeedSearchNews,
)

@chat_agent.instructions
def _date_du_jour() -> str:
    # Évaluée à chaque exécution (contrairement à system_prompt, figé à la création
    # et non rejoué quand un historique est fourni) : la date est donc toujours à jour.
    return instruction_date_du_jour()


chat_agent_2 = Agent(
    build_model(
        {
            "kind": "top-news",
            "parametres": {"source_country": "fr", "language": "fr"},
        }
    ),
    output_type=NeedTopNews | NeedSearchNews,
)


def to_pydantic_history(db_messages: list[Message]) -> list[ModelMessage]:
    """Convertit les messages de la base en historique PydanticAI."""
    history: list[ModelMessage] = []
    for msg in db_messages:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
    return history


def _source_text(source: Source | dict | str) -> str:
    """Retourne le texte d'une source, qu'elle vienne de la base ou de l'API."""
    if isinstance(source, Source):
        return source.content
    if isinstance(source, dict):
        return json.dumps(source, ensure_ascii=False)
    return source


# Sauvegarde des articles reçus dans la base de données et association à la discussion
def save_article(articles: list[Article], session: Session, discussion_id: int) -> None:
    try:
        for article in articles:
            # Recherche si une source avec cette URL existe déjà
            current_source = session.exec(
                select(Source).where(Source.url == article.url)
            ).first()
            if current_source is None:
                current_source = Source(url=article.url, content=article.text)
                session.add(current_source)
                session.flush()
            source_id = current_source.id
            if source_id is None:
                raise RuntimeError(f"Identifiant de source manquant pour {article.url}")

            # On crée une instance intermédiaire qui relie la discussion à la source
            link = session.get(DiscussionSource, (discussion_id, source_id))
            if link is None:
                session.add(
                    DiscussionSource(discussion_id=discussion_id, source_id=source_id)
                )
        session.commit()
    except Exception:
        session.rollback()
        raise


def _articles_from_response(source: NewsApiResponse) -> list[Article]:
    if isinstance(source, TopNewsResponse):
        return [article for cluster in source.top_news for article in cluster.news]
    if isinstance(source, SearchNewsResponse):
        return list(source.news)
    raise TypeError(f"Réponse World News inattendue : {type(source)}")


def call_modele_chat(
    prompt: str,
    session: Session,
    discussion_id: int,
    *,
    agent: Agent | None = None,
    fetch_world_news=None,
) -> ResModel:
    """Fait dialoguer le modèle avec l'utilisateur, en récupérant des news si besoin.

    `agent` et `fetch_world_news` sont injectables pour les tests : aucun appel
    réseau n'est effectué si on les remplace.
    """
    agent = agent or chat_agent
    fetch_world_news = fetch_world_news or call_world_new

    # Récupération des messages de la conversation
    db_messages = session.exec(
        select(Message)
        .where(Message.discussion_id == discussion_id)
        .order_by(Message.created_at, Message.id)
    ).all()

    # Le message courant est parfois déjà en base : on
    # l'exclut de l'historique pour ne pas le dupliquer avec `user_prompt`.
    if db_messages and db_messages[-1].role == "user" and db_messages[-1].content == prompt:
        db_messages = db_messages[:-1]

    db_sources = session.exec(
        select(Source)
        .join(DiscussionSource, DiscussionSource.source_id == Source.id)
        .where(DiscussionSource.discussion_id == discussion_id)
    ).all()

    history = to_pydantic_history(db_messages)
    # On ajoute au prompt les sources déjà enregistrées pour cette discussion.
    sources_existantes = [_source_text(source) for source in db_sources]
    followup = prompt
    if sources_existantes:
        followup += "\n\nDonnées déjà récupérées :\n" + "\n".join(sources_existantes)

    
    conversation = [f"{db_messages!r}\n"]

    for _ in range(MAX_NEWS_ROUNDS):
        conversation.append(followup + "\n\n")

        try:
            run = agent.run_sync(user_prompt=followup, message_history=history)
            result = run.output
        

            # On conserve l'échange complet : le modèle voit sa demande et le résultat.
            history = run.all_messages()
            conversation.append(f"reponse agent :\n {result!r}\n\n")

            if isinstance(result, (NeedTopNews, NeedSearchNews)):
                source = fetch_world_news(result)
                articles = _articles_from_response(source)

                # Sauvegarde dans la base
                save_article(articles, session, discussion_id)
                serialized = [article.model_dump(mode="json") for article in articles]
                conversation.append(
                    "source reçu : \n" + json.dumps(serialized, ensure_ascii=False) + "\n\n"
                )
                
                # On renvoie le résultat au modèle en lui demandant de conclure.
                followup = (
                    f"Résultat de l'appel {result.kind} :\n"
                    f"{json.dumps(serialized, ensure_ascii=False)}\n\n"
                    f"Tu as maintenant les données nécessaires pour répondre à : {prompt}\n"
                    "N'appelle plus l'API : réponds avec une sortie assistant ou reviews."
                )
            elif isinstance(result, ResModel):
                return result

        except ModelHTTPError as e:
            logger.warning("Erreur lors de l'appel du modèle (HTTP %s) : %s", e.status_code, e)
            if e.status_code == 429:
                # Le quota du modèle est dépassé : le client peut réessayer plus tard
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Limite de requêtes du modèle IA atteinte",
                ) from e
            # Inclut le 401 : la clé du serveur est invalide, ce n'est pas la faute
            # de l'utilisateur, donc on ne renvoie pas 401 au frontend
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Erreur du service du modèle IA",
            ) from e
        except UnexpectedModelBehavior as e:
            logger.warning("Réponse inattendue du modèle : %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Réponse invalide du modèle IA",
            ) from e

    logger.warning(
        "Trop de demandes de news successives (%s). Conversation :\n%s",
        MAX_NEWS_ROUNDS,
        "".join(conversation),
    )

    # Le modèle boucle sur ses appels : c'est un défaut de notre côté, pas du client
    raise RuntimeError("Trop de demandes de news successives" )


def call_world_new(result: NeedTopNews | NeedSearchNews) -> NewsApiResponse:
    """Appelle World News API et renvoie la réponse parsée.

    Raises:
        HTTPException: 504 si l'API ne répond pas à temps, 502 pour toute autre
            erreur venant de l'API (HTTP ou réseau).
    """
    params = result.parametres

    # Récupération des paramètres avec les noms alias
    data = params.model_dump(
        by_alias=True,  # clés avec "-" : "headlines-only"
        exclude_none=True,  # ignore les champs non renseignés
        mode="json",  # date -> "2026-10-31"
    )
    # bool reste un bool Python (True), or l'API attend "true" : on convertit
    data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}

    url = f"https://api.worldnewsapi.com/{result.kind}?{urlencode(data)}"
    logger.debug("Appel World News API : %s", url)

    try:
        # On récupère les infos de World News API
        res = requests.get(
            url,
            headers={"x-api-key": os.getenv("API_KEY_WORLD", "")},
            timeout=50,
        )
        # Lève HTTPError pour tout statut 4xx/5xx
        res.raise_for_status()

        logger.debug("Réponse World News API OK (%s)", res.status_code)
        return parse_response(res.json())
    except requests.Timeout as e:
        logger.warning("World News API : timeout : %s", e)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="World News API met trop de temps à répondre",
        ) from e
    except requests.HTTPError as e:
        # Le 401 ici = notre clé API est invalide : on le log, mais le client
        # reçoit quand même un 502 (ce n'est pas son authentification)
        logger.warning("World News API : erreur HTTP %s : %s", e.response.status_code, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erreur de World News API",
        ) from e
    except requests.RequestException as e:
        # Filet de sécurité : ConnectionError, etc. (doit rester en dernier)
        logger.warning("World News API : erreur réseau : %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="World News API injoignable",
        ) from e

    