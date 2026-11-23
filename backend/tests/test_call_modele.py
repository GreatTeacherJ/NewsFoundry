"""Tests du fichier ``src/lib/callModele.py``.

Ce fichier vérifie le code qui fait discuter l'utilisateur avec une IA
(le "modèle") et qui va chercher des articles sur internet quand l'IA
en réclame.

Deux règles importantes dans ces tests :

1. **Aucun test ne se connecte vraiment à internet.** Les morceaux de code
   qui parlent au monde extérieur sont remplacés par des faux, le temps
   du test.
2. **Aucun test n'appelle une vraie IA.** Une vraie IA coûte de l'argent et
   répond quelque chose de différent à chaque fois, donc on ne pourrait rien
   vérifier. On utilise un faux agent qui répond toujours ce qu'on lui a
   préparé.

Pour lancer les tests, depuis le dossier ``backend/`` ::

    uv run pytest tests/test_call_modele.py -q
"""

# --------------------------------------------------------------------------- #
# PETIT LEXIQUE (à lire une fois, il sert dans tout le fichier)
# --------------------------------------------------------------------------- #
# test       : une fonction dont le nom commence par "test_". Personne ne
#              l'appelle dans ce fichier : c'est pytest qui les lance toutes
#              tout seul, puis affiche celles qui échouent.
# assertion  : une ligne "assert ...". Si la condition écrite est fausse,
#              le test échoue. C'est la vérification proprement dite.
# fixture    : une fonction qui PRÉPARE le décor avant un test (une base de
#              données vide, une discussion d'exemple...). pytest l'appelle
#              tout seul et donne son résultat au test.
# doublure   : un faux objet qui remplace un vrai le temps d'un test (faux
#              agent, fausse réponse d'internet). On dit aussi "mock".
# monkeypatch: outil fourni par pytest pour remplacer temporairement une
#              fonction par une autre, puis remettre l'originale à la fin.
# base en
# mémoire    : une base de données qui vit uniquement dans la mémoire de
#              l'ordinateur. Elle est vide au début et disparaît à la fin.

import socket  # Coupe les connexions réseau (voir _no_network plus bas).

import pytest  # Fournit les fixtures et pytest.raises.
import requests  # Parle à internet ; contient aussi le type d'erreur HTTP.
from fastapi import HTTPException  # Exception HTTP à renvoyé au front
from pydantic_ai.messages import ModelRequest, ModelResponse  # enveloppes de message
from sqlalchemy.pool import StaticPool  # voir la fixture "session" plus bas
from sqlmodel import Session, SQLModel, create_engine, select  # accès à la base

from lib import callModele
from lib.callModele import (  # Import direct des fonctions et classes à tester.
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
from models import Discussion, DiscussionSource, Message, Source  # Nos tables.

# --------------------------------------------------------------------------- #
# À quoi servent les imports ci-dessus
# --------------------------------------------------------------------------- #
# ModelRequest / ModelResponse sont des "enveloppes de message" pour l'IA :
#   - ModelRequest  : un message qui VA vers l'IA (la question de l'utilisateur) ;
#   - ModelResponse : un message qui VIENT de l'IA (sa réponse).
#
# Session, SQLModel, create_engine, select servent à parler à la base :
#   - Session       : le "carnet de notes" par lequel on lit et écrit ;
#   - SQLModel      : la classe de base de nos tables ;
#   - create_engine : fabrique le moteur qui relie Python à la base ;
#   - select        : sert à écrire une requête "SELECT ..." (lire des lignes).
#
# On importe aussi le fichier callModele ENTIER (en plus des fonctions), car
# cela permet de remplacer des morceaux à l'intérieur, comme requests.get,
# et d'atteindre l'agent global "chat_agent".


# --------------------------------------------------------------------------- #
# Garde-fou : aucun test ne doit pouvoir joindre un vrai service.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Coupe internet pour TOUS les tests de ce fichier.

    Comment ça marche :

    - ``@pytest.fixture`` : ce n'est pas un test, c'est une préparation.
    - ``autouse=True``    : pytest l'exécute pour tous les tests, même ceux
                            qui ne la demandent pas.
    - ``monkeypatch``     : l'outil qui remplace une fonction, puis remet
                            l'originale en place à la fin du test.

    La fonction ne renvoie rien d'utile : elle sert seulement à installer
    le blocage. Si un test oublie de remplacer un appel réseau, il plantera
    avec un message clair au lieu de contacter vraiment internet.
    """

    def boom(*args, **kwargs):
        # (*args, **kwargs) veut dire "accepte n'importe quels arguments".
        # On ne sait pas comment la vraie fonction sera appelée : peu importe,
        # on veut juste lever une erreur.
        raise AssertionError("Appel réseau interdit pendant les tests")

    # Toutes les fonctions requests.get/post/... passent par Session.request.
    # En bloquant celle-là, on bloque toute la bibliothèque d'un coup.
    monkeypatch.setattr(requests.Session, "request", boom)
    # Deuxième ceinture de sécurité, pour les autres façons de se connecter.
    monkeypatch.setattr(socket.socket, "connect", boom)


# --------------------------------------------------------------------------- #
# Fixtures de base de données.
# --------------------------------------------------------------------------- #
@pytest.fixture
def session():
    """Prépare une base de données vide, neuve pour chaque test.

    Le mot ``yield`` marque une pause :
    - ce qui est écrit AVANT s'exécute avant le test (préparer la base) ;
    - ce qui est écrit APRÈS s'exécute après le test (tout nettoyer).
    """
    engine = create_engine(
        "sqlite://",  # Une adresse sans nom de fichier = base en mémoire.
        connect_args={"check_same_thread": False},  # Autorise plusieurs threads.
        poolclass=StaticPool,
        # StaticPool = "toujours la même ligne téléphonique vers la même base".
        # Sans lui, chaque connexion ouvrirait une base neuve et vide : on
        # enregistrerait un article, puis on ne le retrouverait plus.
    )
    SQLModel.metadata.create_all(engine)  # Crée toutes les tables.
    with Session(engine) as db_session:
        yield db_session  # Voici la base offerte au test qui la demande.
    SQLModel.metadata.drop_all(engine)  # Efface tout : rien ne fuit ailleurs.


@pytest.fixture
def discussion(session):
    """Crée une discussion d'exemple et la range vraiment en base.

    La fixture a besoin de ``session`` : on l'écrit en paramètre, et pytest
    lui fournit automatiquement la base préparée juste au-dessus.
    """
    discussion = Discussion(owner_id=1, title="Test")
    session.add(discussion)
    session.commit()
    # refresh() relit la discussion depuis la base pour récupérer son numéro
    # d'identifiant, qui est attribué automatiquement à l'enregistrement.
    # On en a besoin : les messages et les sources pointent vers ce numéro.
    session.refresh(discussion)
    return discussion


# --------------------------------------------------------------------------- #
# Faux agent : rejoue une liste de sorties et enregistre les appels.
# --------------------------------------------------------------------------- #
class FakeRun:
    """Ce que le faux agent renvoie après avoir été appelé.

    C'est une simple boîte avec deux choses dedans :
    - ``output``    : la réponse de l'IA (par exemple une demande d'articles) ;
    - ``messages``  : l'historique de la conversation après ce tour.
    Le vrai code lit exactement ces deux éléments, donc cela suffit.
    """

    def __init__(self, output, messages):
        self.output = output
        # Le petit underscore de _messages veut dire "attribut privé" :
        # on le lit avec la méthode all_messages(), pas directement.
        self._messages = messages

    def all_messages(self):
        return self._messages


class FakeAgent:
    """Le faux cerveau : il répond une phrase préparée à l'avance.

    On lui donne une liste de réponses au moment de le créer. À chaque appel,
    il rend la première réponse de la liste et la retire, comme on pioche la
    première carte d'un paquet.

    Il garde aussi un journal (``calls``) de tout ce que le code lui a envoyé.
    Cela permet, après le test, de vérifier ce que le vrai agent aurait reçu.
    """

    def __init__(self, outputs):
        # list(...) fait une copie : ainsi, retirer des réponses ne vide pas
        # la liste d'origine qui appartient au test.
        self.outputs = list(outputs)
        self.calls = []

    def run_sync(self, *, user_prompt, message_history=None):
        # Le petit * oblige à écrire le nom de ce qu'on envoie :
        # run_sync(user_prompt=..., message_history=...).
        # C'est la même façon d'appeler que le vrai agent, donc le test reste
        # fidèle au code réel.
        self.calls.append(
            {"user_prompt": user_prompt, "message_history": list(message_history or [])}
        )
        # "message_history or []" veut dire : si l'historique est vide ou
        # absent, utiliser une liste vide. list(...) en fait une copie.

        if not self.outputs:
            # Plus aucune réponse préparée : c'est probablement que le code
            # testé a appelé l'agent plus de fois que prévu. Le message
            # explique clairement le problème.
            raise AssertionError("FakeAgent n'a plus de sortie à rejouer")

        output = self.outputs.pop(0)  # Prend et retire la première réponse.

        # Le vrai agent renvoie l'historique augmenté du tour qui vient de se
        # passer : la question, puis la réponse. On ajoute donc deux messages
        # vides. Leur contenu ne sert à rien ici, seul leur NOMBRE sera
        # vérifié plus tard dans les tests.
        messages = list(message_history or [])
        messages.append(ModelRequest(parts=[]))
        messages.append(ModelResponse(parts=[]))
        return FakeRun(output, messages)


class FakeResponse:
    """Fausse réponse d'internet, pour ne pas vraiment appeler le site.

    Elle contient un contenu (``payload``) et un code (``status_code``) :
    200 veut dire "tout va bien", 500 veut dire "erreur du serveur".
    """

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        # Reproduit ce que fait la vraie bibliothèque requests : elle lève
        # une erreur seulement si le code est 400 ou plus.
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def article_payload(article_id=1, url="https://exemple.fr/article-1"):
    """Fabrique un exemple d'article, au format renvoyé par l'API.

    C'est une fonction (et pas une simple variable) pour pouvoir créer
    plusieurs articles différents sans réécrire tout le dictionnaire.
    """
    return {
        "id": article_id,
        "title": "Titre de l'article",
        "text": "Contenu de l'article",
        "url": url,
        "publish_date": "2025-09-30",
    }


# Deux exemples de réponses de l'API, avec des formes différentes.
# C'est justement cette différence qui permet au code de reconnaître
# de quel type de réponse il s'agit.
TOP_NEWS_PAYLOAD = {
    "top_news": [{"news": [article_payload()]}],  # des groupes, contenant des articles
    "language": "fr",
    "country": "fr",
}

SEARCH_NEWS_PAYLOAD = {
    "offset": 0,  # champs présents seulement dans une recherche
    "number": 1,
    "available": 1,
    "news": [article_payload()],  # une simple liste d'articles
}


def top_news_request(**kwargs):
    """Prépare une demande de "unes" déjà valide.

    Les noms avec un tiret ("source-country") sont ceux attendus par l'API.
    Le ``**kwargs`` permet d'ajouter ou de remplacer un champ quand un test
    en a besoin, sans réécrire toute la demande.
    """
    params = {"source-country": "fr", "language": "fr", **kwargs}
    return NeedTopNews(parametres=ParamsTopNews(**params))


# --------------------------------------------------------------------------- #
# Teste de parse_response : reconnaître une réponse de l'API et la ranger dans un objet.
# --------------------------------------------------------------------------- #
def test_parse_response_top_news():
    """Une réponse de type "unes" doit être reconnue comme telle."""
    result = parse_response(TOP_NEWS_PAYLOAD)
    # isinstance vérifie le type de l'objet obtenu.
    assert isinstance(result, TopNewsResponse)
    # On vérifie aussi que l'article a bien été rangé au bon endroit :
    # groupes de news -> premier groupe -> premier article -> adresse web.
    assert result.top_news[0].news[0].url == "https://exemple.fr/article-1"


def test_parse_response_search_news():
    """Une réponse de type "recherche" doit être reconnue comme telle."""
    result = parse_response(SEARCH_NEWS_PAYLOAD)
    assert isinstance(result, SearchNewsResponse)
    assert result.news[0].title == "Titre de l'article"


# --------------------------------------------------------------------------- #
# call_world_new : construire et envoyer la demande à l'API.
# --------------------------------------------------------------------------- #
def test_call_world_new_construit_la_requete(monkeypatch):
    """On vérifie l'adresse, les en-têtes et le délai envoyés à l'API.

    Aucune vraie requête : on remplace requests.get par notre fausse fonction
    ``fake_get``, qui note ce qu'elle reçoit puis renvoie une fausse réponse.
    """
    captured = {}  # Un panier vide que la fausse fonction remplira.

    def fake_get(url, headers=None, timeout=None):
        # On recopie les arguments reçus dans le panier.
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(TOP_NEWS_PAYLOAD)

    # Remplace requests.get par fake_get. Sans parenthèses après fake_get :
    # on installe la fonction elle-même, on ne l'appelle pas ici.
    monkeypatch.setattr(callModele.requests, "get", fake_get)
    # Fixe la clé d'API pour que le résultat soit toujours le même.
    monkeypatch.setenv("API_KEY_WORLD", "test-key")

    request = top_news_request(
        **{"headlines-only": True, "max-news-per-cluster": 3, "date": "2025-09-30"}
    )
    # C'est MAINTENANT que fake_get est vraiment exécutée, par call_world_new.
    result = call_world_new(request)

    assert isinstance(result, TopNewsResponse)
    # L'adresse doit commencer par la bonne partie de l'API.
    assert captured["url"].startswith("https://api.worldnewsapi.com/top-news?")
    # On cherche un morceau dans l'adresse (in) au lieu de comparer toute
    # l'adresse (==) : cela évite que le test casse si l'ordre des paramètres
    # change, ou si un paramètre sans importance est ajouté un jour.
    assert "source-country=fr" in captured["url"]
    # Vérifie que True est bien transformé en "true" et pas en "True".
    assert "headlines-only=true" in captured["url"]
    assert "max-news-per-cluster=3" in captured["url"]
    # Vérifie que la date fait l'aller-retour sans être déformée.
    assert "date=2025-09-30" in captured["url"]
    # La clé d'API doit être transmise dans un en-tête de la requête.
    assert captured["headers"] == {"x-api-key": "test-key"}
    # Le délai maximum d'attente est de 50 secondes.
    assert captured["timeout"] == 50


def test_call_world_new_search_news(monkeypatch):
    """Une demande de recherche doit utiliser la bonne adresse de l'API."""
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url  # Ici, seule l'adresse nous intéresse.
        return FakeResponse(SEARCH_NEWS_PAYLOAD)

    monkeypatch.setattr(callModele.requests, "get", fake_get)

    request = NeedSearchNews(parametres=ParamsSearchNews(text="climat"))
    result = call_world_new(request)

    assert isinstance(result, SearchNewsResponse)
    assert captured["url"].startswith("https://api.worldnewsapi.com/search-news?")
    assert "text=climat" in captured["url"]


def test_call_world_new_propage_les_erreurs_http(monkeypatch):
    """Si le site répond par une erreur, le code doit la signaler aussi.

    Le lambda est une mini-fonction écrite en une ligne : ici, elle renvoie
    toujours une fausse réponse avec le code 500 (erreur serveur).
    """
    monkeypatch.setattr(
        callModele.requests, "get", lambda *args, **kwargs: FakeResponse({}, 500)
    )
    # pytest.raises veut dire : "on s'attend à une erreur". Si aucune erreur
    # n'arrive, c'est le test lui-même qui échoue.
    with pytest.raises(HTTPException) as excinfo:
        call_world_new(NeedSearchNews(parametres=ParamsSearchNews(text="climat")))

    # L'erreur HTTP de l'API est traduite en 502 avec un message lisible :
    # le détail technique reste dans les logs, pas dans la réponse au client.
    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "Erreur de World News API"


# --------------------------------------------------------------------------- #
# save_article : enregistrer les articles sans créer de doublons.
# --------------------------------------------------------------------------- #
def test_save_article_cree_puis_reutilise_la_source(session, discussion):
    """Le même article enregistré deux fois ne doit apparaître qu'une fois.

    C'est ce qu'on appelle "idempotent" : refaire la même action ne change
    rien de plus après la première fois.
    """
    # Les ** servent à ranger chaque case du dictionnaire dans le champ qui
    # porte le même nom.
    article = Article(**article_payload())

    save_article([article], session, discussion.id)  # Premier appel : crée.
    save_article([article], session, discussion.id)  # Deuxième : ne duplique pas.

    # On relit la BASE de données (et non les objets Python) : c'est la
    # preuve que l'enregistrement a vraiment eu lieu.
    sources = session.exec(select(Source)).all()
    links = session.exec(select(DiscussionSource)).all()

    # Une seule source, parce que le code cherche d'abord si une adresse
    # identique existe déjà avant d'en créer une nouvelle.
    assert len(sources) == 1
    assert sources[0].url == article.url
    assert sources[0].content == article.text
    # Un seul lien entre la discussion et la source, lui aussi.
    assert len(links) == 1
    assert links[0].source_id == sources[0].id
    assert links[0].discussion_id == discussion.id


# --------------------------------------------------------------------------- #
# to_pydantic_history : transformer nos messages en messages pour l'IA.
# --------------------------------------------------------------------------- #
def test_to_pydantic_history():
    """Un message "user" devient une question ; les autres, une réponse.

    Les messages créés ici ne sont pas enregistrés en base : la fonction ne
    lit que leur rôle ("user" ou "assistant") et leur contenu.
    """
    history = to_pydantic_history(
        [
            Message(discussion_id=1, role="user", content="Salut"),
            Message(discussion_id=1, role="assistant", content="Bonjour"),
        ]
    )

    # Le message de l'utilisateur part vers l'IA (ModelRequest).
    assert isinstance(history[0], ModelRequest)
    assert history[0].parts[0].content == "Salut"
    # Le message de l'assistant vient de l'IA (ModelResponse).
    assert isinstance(history[1], ModelResponse)
    assert history[1].parts[0].content == "Bonjour"


# --------------------------------------------------------------------------- #
# call_modele_chat : la conversation complète avec l'IA.
# --------------------------------------------------------------------------- #
def test_call_modele_chat_repond_sans_source(session, discussion):
    """Quand l'IA répond directement, on ne va PAS chercher d'articles."""
    expected = ResModel(kind="assistant", content="Réponse")

    def fetch(_):
        # Test "négatif" : cette fausse fonction plante si on l'appelle.
        # C'est une façon très sûre de prouver qu'un appel n'a pas eu lieu.
        # Le nom _ veut dire "paramètre dont je ne me sers pas".
        raise AssertionError("Aucun appel World News ne devait être fait")

    result= call_modele_chat(
        "Bonjour",
        session,
        discussion.id,
        agent=FakeAgent([expected]),  # Une seule réponse préparée : ResModel.
        fetch_world_news=fetch,  # Fourni, mais ne doit jamais servir.
    )

    # Avec Pydantic, == compare le CONTENU des objets, pas leur adresse en
    # mémoire : deux objets avec les mêmes champs sont considérés égaux.
    assert result == expected


def test_call_modele_chat_ignore_le_message_courant_deja_en_base(session, discussion):
    """Le message en cours ne doit pas être envoyé deux fois à l'IA.

    Dans la vraie application, la question de l'utilisateur est enregistrée
    en base AVANT l'appel à l'IA. Si on ne faisait rien, l'IA recevrait la
    question à la fois dans l'historique et dans le nouveau message.
    """
    session.add(Message(discussion_id=discussion.id, role="user", content="Bonjour"))
    session.commit()

    agent = FakeAgent([ResModel(kind="assistant", content="ok")])
    call_modele_chat("Bonjour", session, discussion.id, agent=agent)

    # Un historique vide prouve que le message en double a bien été retiré.
    assert agent.calls[0]["message_history"] == []


def test_call_modele_chat_recupere_les_news_puis_conclut(session, discussion):
    """Scénario complet en deux temps : l'IA demande des articles, puis conclut.

    FakeAgent reçoit deux réponses préparées : d'abord une demande de "unes",
    puis une réponse finale. C'est exactement la conversation qu'on veut tester.
    """
    request = top_news_request()
    final = ResModel(kind="reviews", content="Synthèse")
    agent = FakeAgent([request, final])
    fetched = []  # Journal des demandes reçues par la fausse API.

    def fetch(received):
        fetched.append(received)
        # On utilise le VRAI parse_response : seul l'appel internet est faux.
        # On vérifie ainsi toute la chaîne : demande -> lecture -> sauvegarde.
        return parse_response(TOP_NEWS_PAYLOAD)

    result = call_modele_chat(
        "Actualités",
        session,
        discussion.id,
        agent=agent,
        fetch_world_news=fetch,
    )

    assert result == final
    # Une seule demande, et c'est bien celle que l'IA avait rédigée.
    assert fetched == [request]
    # On vérifie que les articles sont vraiment enregistrés dans la base.
    assert len(session.exec(select(Source)).all()) == 1
    assert len(session.exec(select(DiscussionSource)).all()) == 1

    # --- Ce qui se passe au DEUXIÈME appel à l'IA -------------------------- #
    # Le texte envoyé à l'IA annonce le résultat de la demande...
    assert "Résultat de l'appel top-news" in agent.calls[1]["user_prompt"]
    # ...et contient bien les articles, pas juste une phrase vague.
    assert "Titre de l'article" in agent.calls[1]["user_prompt"]
    # L'IA a reçu l'échange précédent (deux messages ajoutés par FakeAgent),
    # donc elle garde le fil de la conversation.
    assert len(agent.calls[1]["message_history"]) == 2


def test_call_modele_chat_recupere_une_recherche_puis_conclut(session, discussion):
    """Même scénario, mais avec une recherche au lieu des "unes"."""
    request = NeedSearchNews(parametres=ParamsSearchNews(text="climat"))
    final = ResModel(kind="assistant", content="Voici les résultats")
    agent = FakeAgent([request, final])

    result = call_modele_chat(
        "Cherche des news sur le climat",
        session,
        discussion.id,
        agent=agent,
        # Une mini-fonction (lambda) suffit : on n'a rien à inspecter ici.
        fetch_world_news=lambda _: parse_response(SEARCH_NEWS_PAYLOAD),
    )

    assert result == final
    assert len(session.exec(select(Source)).all()) == 1


def test_call_modele_chat_limite_les_demandes_de_news(session, discussion):
    """Si l'IA demande des articles sans jamais conclure, on l'arrête.

    Sans cette limite, la conversation pourrait tourner indéfiniment.
    """
    request = top_news_request()
    # [request] * 3 fabrique trois fois la même réponse : l'IA redemande
    # toujours des articles et ne donne jamais sa conclusion.
    agent = FakeAgent([request] * MAX_NEWS_ROUNDS)
    fetched = []

    def fetch(received):
        fetched.append(received)
        return parse_response(TOP_NEWS_PAYLOAD)

    # On s'attend à une erreur. Le paramètre match vérifie en plus que le
    # message de l'erreur contient bien "Trop de demandes".
    with pytest.raises(RuntimeError, match="Trop de demandes"):
        call_modele_chat(
            "Actualités",
            session,
            discussion.id,
            agent=agent,
            fetch_world_news=fetch,
        )

    # Cette vérification est APRÈS le bloc ci-dessus, donc elle s'exécute une
    # fois l'erreur attrapée. Elle prouve que l'arrêt a eu lieu après
    # exactement 3 tentatives : ni une seule, ni quatre.
    assert len(fetched) == MAX_NEWS_ROUNDS


# --------------------------------------------------------------------------- #
# Date du jour : l'IA doit toujours connaître la date actuelle.
# --------------------------------------------------------------------------- #
def test_instruction_date_du_jour_formate_la_date_en_francais():
    """La date est écrite en français ET au format technique AAAA-MM-JJ."""
    # Imports écrits ici (et pas en haut du fichier) : ils ne servent que
    # dans ces tests de date.
    from datetime import UTC, datetime

    from lib.prompt_systeme import instruction_date_du_jour

    # On donne une date précise en paramètre. Ainsi, le test donnera toujours
    # le même résultat, quel que soit le jour où on le lance.
    texte = instruction_date_du_jour(datetime(2026, 11, 16, 10, 0, tzinfo=UTC))

    # Version lisible par un humain : utile pour comprendre "hier", "lundi"...
    assert "lundi 16 novembre 2026" in texte
    # Version technique : utile pour remplir les paramètres de l'API.
    assert "2026-11-16" in texte


def test_instruction_date_du_jour_utilise_le_fuseau_de_paris():
    """La date doit être celle de Paris, pas celle de Londres (UTC)."""
    from datetime import UTC, datetime

    from lib.prompt_systeme import instruction_date_du_jour

    # 23h30 à Londres le 31 décembre = 00h30 à Paris le 1er janvier.
    # Sans conversion, le texte dirait "jeudi 31 décembre 2026" : faux.
    texte = instruction_date_du_jour(datetime(2026, 12, 31, 23, 30, tzinfo=UTC))

    assert "vendredi 1 janvier 2027" in texte



def test_l_agent_recoit_la_date_du_jour_meme_avec_un_historique():
    """L'IA reçoit bien ses consignes et la date, même en pleine discussion.

    C'est le test le plus complet : on utilise le vrai agent, avec ses vraies
    consignes. Seule l'IA elle-même est remplacée par une fonction Python.
    """
    from datetime import date

    from pydantic_ai.models.function import FunctionModel

    from lib.prompt_systeme import PROMPT_SYSTEME_BASE

    seen = []  # On y rangera les consignes réellement envoyées à l'IA.

    def model_function(messages, info):
        from pydantic_ai.messages import ModelResponse, ToolCallPart

        # "messages" est la liste de tout ce que l'agent s'apprêtait à
        # envoyer. Le dernier élément contient les consignes (le texte qui
        # explique à l'IA son rôle) et la date du jour.
        seen.append(messages[-1].instructions)
        # La bibliothèque présente les formats de réponse possibles comme des
        # "outils". L'IA doit en choisir un pour répondre dans le bon format.
        tool = info.output_tools[0]
        # On imite ce choix, avec un contenu valable pour ResModel
        # (un "kind" et un "content"). Cela produit une réponse correcte
        # sans appeler de vraie IA.
        return ModelResponse(
            parts=[ToolCallPart(tool.name, {"kind": "assistant", "content": "ok"})]
        )

    history = to_pydantic_history([Message(discussion_id=1, role="user", content="Salut")])
    # override remplace le vrai modèle par le nôtre, le temps du bloc with.
    # À la sortie du bloc, le modèle d'origine est remis en place.
    with callModele.chat_agent.override(model=FunctionModel(model_function)):
        # On fournit un historique non vide : c'est justement le cas où l'on
        # veut s'assurer que les consignes ne sont pas oubliées.
        callModele.chat_agent.run_sync("Quoi de neuf ?", message_history=history)

    # Si cette liste est vide, notre fausse IA n'a jamais été appelée.
    assert seen, "le modèle n'a pas été appelé"
    # La date est bien présente dans les consignes...
    assert "Date du jour" in seen[0]
    # ...avec l'année actuelle. (On ne compare que l'année pour que le test
    # reste vrai toute l'année.)
    assert date.today().strftime("%Y") in seen[0]
    # Et le texte de rôle de l'IA est toujours là. On compare seulement le
    # début du texte : la suite peut être enrichie sans casser ce test.
    assert PROMPT_SYSTEME_BASE[:60] in seen[0]
