import os

from lib.prompt_systeme import PROMPT_SYSTEME_BASE
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel, TypeAdapter
import requests
from pydantic import BaseModel, ConfigDict, Field
import json
from dotenv import load_dotenv  # uv add python-dotenv
from typing import Literal
from datetime import date as dt
from urllib.parse import urlencode
from models import Message, Source, DiscussionSource
from sqlmodel import Session, select

#Rajout pour utiliser les endpoint de mammouth
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart,
)

from lib.prompt_systeme import PROMPT_SYSTEME_BASE

# Charge le .env AVANT toute lecture de variable d'environnement
load_dotenv()


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

    text :str | None = None
    text_match_indexes : str | None = Field(default=None, alias="text-match-indexes")
    source_country: str | None = Field(default=None, alias="source-country")
    language : str | None = None
    earliest_publish_date : dt| None = Field(default=None, alias="earliest-publish-date")
    latest_publish_date :  dt| None = Field(default=None, alias="latest-publish-date")
    categories : str | None = None


class ResModel(BaseModel):
    kind: Literal["reviews", "assistant"]
    content : str

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

API_KEY_WORLD = os.getenv("API_KEY_WORLD", "")
MAMMOUTH_KEY = os.getenv("MAMMOUTH_KEY")

MAX_NEWS_ROUNDS = 3

review = """**REVUE DE PRESSE POLITIQUE - 30 Septembre 2025**

**Synthèse hebdomadaire des principales actualités politiques :**

• **Réforme économique** : Le gouvernement a présenté son plan de relance économique avec des mesures ciblées sur l'emploi et l'innovation. Les réactions sont mitigées entre opposition et majorité.

• **Relations internationales** : Préparation du sommet européen avec focus sur les questions énergétiques et la coopération en matière de défense.

• **Politique intérieure** : Débats parlementaires sur la réforme du système de santé, avec des amendements proposés par différents groupes politiques.

**Perspectives** : Les prochaines semaines seront cruciales pour l'adoption des mesures proposées et leur impact sur l'opinion publique."""

# "test" = faux modèle (aucune clé requise), sinon un vrai modèle
MODEL_NAME = os.getenv("AI_MODEL", "test")

MAMMOUTH = OpenAIChatModel(
    'mammouth-recommended',
    provider=OpenAIProvider(base_url="https://api.mammouth.ai/v1", api_key=MAMMOUTH_KEY),
)

model = (
    TestModel(
        custom_output_args={"kind": "reviews", "content": review})
    if MODEL_NAME == "test"
    else MAMMOUTH
)

chat_agent = Agent(
    model,
    system_prompt=PROMPT_SYSTEME_BASE,
    output_type= ResModel | NeedTopNews | NeedSearchNews 
)

model_2 = (TestModel(custom_output_args={"kind": "top-news", "parametres": {"source_country": "fr", "language": "fr"}})if MODEL_NAME == "test"
    else MAMMOUTH)

chat_agent_2 = Agent(
    model_2,
    output_type=NeedTopNews | NeedSearchNews
)

def to_pydantic_history(db_messages:list[Message]) -> list[ModelMessage]:
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

#Sauvegarde des articles reçu dans la base de donné et asociation à la discussion
def save_article(articles:list[Article], session:Session, discussion_id:int):
    for article in articles:
        #recherche si un url existe déja
        current_source = session.exec(select(Source).where(Source.url == article.url)).first()
        src_id:int = None
        #si il existe on recupére l'id de la source
        if(current_source):
            src_id = current_source.id
            #sinon on créer l'artcile avant de récupérer l'id de la nouvelle source
        else:
            source = Source(article.url, article.text)
            session.add(source)
            session.commit()
            session.refresh(source)
            src_id = source.id
        #On créer une instance intermediaire qui relie la discution à la source
        discussion_source = DiscussionSource(discussion_id, src_id.id)
        session.add(discussion_source)
        session.commit()
        session.refresh(discussion_source)

def call_modele_chat(
    prompt: str,
    session: Session,
    discussion_id: int,  
) -> tuple[ResModel, list[str]]:

        #Récupération des messages de la conversation
    db_messages = session.exec(
        select(Message).where(Message.discussion_id == discussion_id).order_by(Message.created_at, Message.id)
    ).all()
    db_source = session.exec(select(Article)
    .join(DiscussionSource, DiscussionSource.article_id == Article.id)
    .where(DiscussionSource.discussion_id == discussion_id)).all()
    
    history = to_pydantic_history(db_messages or [])
    # On ajoute au prompt les sources déjà enregistrées pour cette discussion.
    sources_existantes = [_source_text(source) for source in (db_source or [])]
    followup = prompt
    if sources_existantes:
        followup += "\n\nDonnées déjà récupérées :\n" + "\n".join(sources_existantes)

    new_sources: list[str] = []

    conversation:str = f"{db_messages!r}\n"
    for _ in range(MAX_NEWS_ROUNDS):

        conversation += followup  + "\n\n"

        run = chat_agent.run_sync(user_prompt=followup, message_history=history)
        result = run.output

        # On conserve l'échange complet : le modèle voit sa demande et le résultat.
        history = run.all_messages()

        conversation += f"reponse agent :\n {result!r}\n\n"

        match result:
            case NeedTopNews() | NeedSearchNews():
                source = call_world_new(result)
                #Liste de tous les articles récupérer
                articles:list[Article] = []
                #si la reponse provient de topNews
                if(isinstance(TopNewsResponse)):                    
                    for clusters in source.top_news:
                        articles = clusters     
                elif(isinstance(SearchNewsResponse)):
                    articles = source.news
                #sauvegarde dans la db
                save_article(articles,session,discussion_id)

                conversation += "source reçu : \n" + json.dumps(articles) + "\n\n"
                new_sources.append(json.dumps(articles, ensure_ascii=False))

                # On renvoie le résultat au modèle en lui demandant de conclure.
                followup = (
                    f"Résultat de l'appel {result.kind} :\n"
                    f"{json.dumps(articles, ensure_ascii=False)}\n\n"
                    f"Tu as maintenant les données nécessaires pour répondre à : {prompt}\n"
                    "N'appelle plus l'API : réponds avec une sortie assistant ou reviews."
                )
            case ResModel():
                return result
            case _:
                raise TypeError(f"Sortie inattendue : {type(result)}")

    with open("conversation.txt","w",encoding="utf-8") as f:
        f.write(conversation)

    raise RuntimeError("Trop de demandes de news successives")       

def call_world_new(result:NeedTopNews | NeedSearchNews)->NewsApiResponse:        

    params = result.parametres   
    
    #récupération des parametre avec les nom alias
    data = params.model_dump(
        by_alias=True,      # clés avec "-" : "headlines-only"
        exclude_none=True,  # ignore les champs non renseignés
        mode="json",        # date -> "2026-10-31"
)
    # bool reste un bool Python (True), or l'API attend "true" : on convertit   
    data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}

    url = f"https://api.worldnewsapi.com/{result.kind}?{urlencode(data)}" 
    print("url : ", url)           

    #on récupére les infos de worls News api
    res = requests.get(url, headers={"x-api-key": API_KEY_WORLD}, timeout=50)

    res.raise_for_status()       
    print("reponse api news world ok !", res)
    return parse_response(res.json())

if __name__ == '__main__':
    
    """
    prompt = "teste prompt"
    result, _ = call_modele_chat("teste prompt")
    print(f"reponse modele : {result}")"""
