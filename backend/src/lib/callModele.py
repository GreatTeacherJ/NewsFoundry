import os

from lib.prompt_systeme import PROMPT_SYSTEME_BASE, PROMPT_SYSTEME_WITH_NEWS

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
import requests
from pydantic import BaseModel, ConfigDict, Field
import json
from dotenv import load_dotenv  # uv add python-dotenv
from typing import Literal
from datetime import date as dt
from urllib.parse import urlencode
from models import utc_now

# Charge le .env AVANT toute lecture de variable d'environnement
load_dotenv()


class ParamsTopNews(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
     
    source_country : str = Field(alias="source-country")
    language : str
    date : dt | None = None
    headlines_only : bool | None = Field(default=None, alias="headlines-only")
    max_news_per_cluster : int | None = Field(default=None, alias="max-news-per-cluster")

class ParamsSearchNews(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text :str | None = None
    text_match_indexes : str | None = Field(default=None, alias="text-match-indexes")
    source_country: str | None = Field(default=None, alias="source-country")
    language : str | None = None
    earliest_publish_date : dt| None = Field(default=None, alias="earliest-publish-date")
    latest_publish_date :  dt| None = Field(default=None, alias="latest-publish-date")
    categories : str | None = None

class NeedWorld(BaseModel):
    kind: Literal["need_world"] = "need_world"
    appel: Literal["top-news", "search-news"]
    parametres: ParamsTopNews | ParamsSearchNews

class ResModel(BaseModel):
    kind: Literal["reviews", "assistant"]
    content : str


API_KEY_WORLD = os.getenv("API_KEY_WORLD", "")

# "test" = faux modèle (aucune clé requise), sinon un vrai modèle
MODEL_NAME = os.getenv("AI_MODEL", "test")

model = TestModel(custom_output_args={"kind":"content","content":"Je suis un agent teste aucune IA n'est chargées, le message suivant bien reçu : "}) if MODEL_NAME == "test" else MODEL_NAME

chat_agent = Agent(
    model,
    system_prompt="Tu es un assistant de revue de presse.",
    output_type= [NeedWorld, ResModel]    
)

model_2 = TestModel(custom_output_args={"appel": "top-news", "parametres": {"source_country": "fr", "language": "fr"}})

chat_agent_2 = Agent(
    model_2,
    output_type=NeedWorld
)

review = {"title":"", "date":utc_now, "content":"""**REVUE DE PRESSE POLITIQUE - 30 Septembre 2025**

**Synthèse hebdomadaire des principales actualités politiques :**

• **Réforme économique** : Le gouvernement a présenté son plan de relance économique avec des mesures ciblées sur l'emploi et l'innovation. Les réactions sont mitigées entre opposition et majorité.

• **Relations internationales** : Préparation du sommet européen avec focus sur les questions énergétiques et la coopération en matière de défense.

• **Politique intérieure** : Débats parlementaires sur la réforme du système de santé, avec des amendements proposés par différents groupes politiques.

**Perspectives** : Les prochaines semaines seront cruciales pour l'adoption des mesures proposées et leur impact sur l'opinion publique."""}


def call_modele_chat(prompt:str) -> tuple[ResModel, str]:
    #on commence par envoyer la demande de l'utilisateur au model
    print("prompt reçu : ", prompt)
    res = chat_agent_2.run_sync(user_prompt=prompt, instructions=PROMPT_SYSTEME_BASE)       
    result = res.output
    print("Premiére reponse model reçu : ", result)

    final_res:str
    res_new:str | None = None

    match result : 
        # Si le model à besoin d'info en plus il renvoie un type NeedWorld
        case NeedWorld():
            final_res, res_new = call_world_new(result.parametres)
        case ResModel():
            final_res =  result

    return final_res, json.dumps(res_new)

def call_world_new(result:NeedWorld):        

    params = result.parametres   
    
    #récupération des parametre avec les nom alias
    data = params.model_dump(
        by_alias=True,      # clés avec "-" : "headlines-only"
        exclude_none=True,  # ignore les champs non renseignés
        mode="json",        # date -> "2026-10-31"
)
    # bool reste un bool Python (True), or l'API attend "true" : on convertit   
    data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}
    query = urlencode(data) 
        
    url = "https://api.worldnewsapi.com/"+result.appel +"?"+ query
    print("url : ", url)               
    
    url = "https://api.worldnewsapi.com/top-news?source-country=fr&language=fr&date=2026-10-30"            

    headers = {
        'x-api-key': API_KEY_WORLD
    }
    #on récupére les infos de worls News api
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        return f"Error: {res}"
    res_new = res.json()        

    prompt_systeme_with_news = PROMPT_SYSTEME_WITH_NEWS+ json.dumps(res_new)
    res = chat_agent.run_sync(user_prompt=prompt, instructions=prompt_systeme_with_news)
    return res.output, res_new

if __name__ == '__main__':
    prompt = "teste prompt"
    result = call_modele_chat("teste prompt")
    print(f"reponse modele : {result}")