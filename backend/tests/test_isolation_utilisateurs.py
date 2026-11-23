# --------------------------------------------------------------------------- #
# TESTS AJOUTÉS — isolation entre utilisateurs (chargement / modification)
# --------------------------------------------------------------------------- #
# Ce fichier vérifie qu'un utilisateur ne peut ni LIRE ni MODIFIER les chats
# d'un autre utilisateur :
#   1. lire les messages d'une discussion qui ne nous appartient pas ;
#   2. modifier / supprimer le message d'un autre utilisateur ;
#   3. lire / modifier / supprimer la revue de presse d'un autre utilisateur.
#
# Règle vérifiée : la réponse est 404 (et non 403). Un 403 dirait "ça existe,
# mais ce n'est pas à toi" et révélerait donc que la ressource existe. Le 404
# ne donne aucune information à un utilisateur curieux.
#
# Chaque test vérifie aussi que les données du propriétaire sont restées
# intactes après la tentative : la tentative échoue ET ne modifie rien.
#
# --------------------------------------------------------------------------- #

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from routers import base

# Base de données en mémoire, propre à CE fichier : elle n'interfère pas avec
# celle de tests/test_api.py. "sqlite://" sans nom de fichier = base en RAM.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    # StaticPool = toujours la même connexion, donc la même base en mémoire.
    # Sans lui, chaque connexion ouvrirait une base neuve et vide.
)


def override_get_session():
    """Remplace la vraie base par notre base de test, le temps d'une requête."""
    with Session(engine) as session:
        yield session


# Application dédiée aux tests : uniquement les routes dont on a besoin.
# On n'utilise pas main.app, pour éviter le conflit expliqué en tête de fichier.
app = FastAPI()
app.include_router(base.router)
app.dependency_overrides[base.get_session] = override_get_session
client = TestClient(app)


def setup_function():
    """Avant chaque test : on repart d'une base vide (tables recréées)."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def auth_headers(email: str) -> dict[str, str]:
    """Crée un utilisateur, le connecte, renvoie son en-tête HTTP.

    On vérifie au passage que l'inscription répond 201 et la connexion 200.
    Le résultat est au format attendu par l'API : "Bearer <jeton>".
    """
    response = client.post(
        "/auth/register", json={"email": email, "password": "secure-password"}
    )
    assert response.status_code == 201

    response = client.post(
        "/auth/login", json={"email": email, "password": "secure-password"}
    )
    assert response.status_code == 200

    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_un_utilisateur_ne_peut_pas_lire_les_messages_d_un_autre():
    """Charger les messages d'un chat qui ne nous appartient pas -> 404.

    Scénario :
    - "owner" crée une discussion et y écrit un message ;
    - "intrus" essaie de lire les messages de cette discussion ;
    - l'API refuse, et la discussion du propriétaire n'a pas bougé.
    """
    # Deux comptes distincts. Chaque test repart d'une base vide grâce à
    # setup_function(), donc les adresses e-mail peuvent être réutilisées.
    owner = auth_headers("owner-messages@example.com")
    intrus = auth_headers("intrus-messages@example.com")

    # Le propriétaire crée son chat. On récupère son identifiant (id) dans
    # la réponse JSON pour construire les URL suivantes.
    discussion_id = client.post(
        "/discussions", headers=owner, json={"title": "Privé"}
    ).json()["id"]

    # On écrit un message dans ce chat. Cela déclenche aussi la réponse de
    # l'assistant de test (le faux modèle configuré par AI_MODEL=test).
    # L'appel renvoie 201 et une liste de deux messages : question + réponse.
    assert client.post(
        f"/discussions/{discussion_id}/messages",
        headers=owner,
        json={"content": "Secret"},
    ).status_code == 201

    # L'intrus tente de lire les messages de ce chat avec SON jeton.
    response = client.get(f"/discussions/{discussion_id}/messages", headers=intrus)

    # 404 = "je ne trouve pas cette discussion", volontairement identique au
    # cas "cette discussion n'existe pas" : rien n'est révélé à l'intrus.
    assert response.status_code == 404

    # Vérification de l'absence d'effet de bord : le propriétaire retrouve
    # bien ses deux messages (sa question et la réponse de l'assistant).
    messages = client.get(
        f"/discussions/{discussion_id}/messages", headers=owner
    ).json()
    assert len(messages) == 2


def test_un_utilisateur_ne_peut_pas_modifier_ou_supprimer_un_message_d_un_autre():
    """Modifier ou supprimer le message d'un autre utilisateur -> 404.

    Ce test couvre deux actions différentes (PATCH puis DELETE) sur la même
    ressource, et vérifie que le message est toujours là, inchangé, à la fin.
    """
    owner = auth_headers("owner-edit@example.com")
    intrus = auth_headers("intrus-edit@example.com")

    discussion_id = client.post(
        "/discussions", headers=owner, json={"title": "Privé"}
    ).json()["id"]
    client.post(
        f"/discussions/{discussion_id}/messages",
        headers=owner,
        json={"content": "Secret"},
    )

    # On récupère l'identifiant du premier message de la liste, c'est-à-dire
    # la question écrite par le propriétaire (elle précède la réponse).
    message_id = client.get(
        f"/discussions/{discussion_id}/messages", headers=owner
    ).json()[0]["id"]

    # Tentative de modification avec le jeton de l'intrus.
    # Remarque : le corps envoyé n'a aucune importance ici. Le contrôle de
    # propriété est fait AVANT la lecture du contenu, donc l'API répond 404
    # sans même regarder ce que l'intrus essaie d'écrire.
    assert client.patch(
        f"/discussions/{discussion_id}/messages/{message_id}",
        headers=intrus,
        json={"content": "Piraté"},
    ).status_code == 404

    # Tentative de suppression avec le jeton de l'intrus.
    assert client.delete(
        f"/discussions/{discussion_id}/messages/{message_id}", headers=intrus
    ).status_code == 404

    # Le message doit être toujours présent ET toujours avec son texte
    # d'origine. Sans cette vérification, on saurait seulement que l'API a
    # répondu 404, pas qu'elle n'a rien modifié au passage.
    messages = client.get(
        f"/discussions/{discussion_id}/messages", headers=owner
    ).json()
    assert any(message["content"] == "Secret" for message in messages)


def test_un_utilisateur_ne_peut_pas_toucher_aux_revues_de_presse_d_un_autre():
    """Lire, modifier ou supprimer la revue de presse d'un autre -> 404.

    Une revue de presse est créée à partir du dernier message de rôle
    "reviews" de la discussion. Il faut donc d'abord envoyer un message :
    l'assistant de test répond avec ce rôle, ce qui rend la création possible.
    """
    owner = auth_headers("owner-review@example.com")
    intrus = auth_headers("intrus-review@example.com")

    discussion_id = client.post(
        "/discussions", headers=owner, json={"title": "Privé"}
    ).json()["id"]

    # Message indispensable : sans réponse de rôle "reviews", la création
    # d'une revue de presse échouerait avec un 409 (conflit).
    client.post(
        f"/discussions/{discussion_id}/messages",
        headers=owner,
        json={"content": "Rédige une revue"},
    )

    # Le propriétaire crée la revue de presse (copie du message "reviews").
    review_id = client.post(
        f"/discussions/{discussion_id}/press-reviews", headers=owner
    ).json()["id"]

    # 1) Lecture par l'intrus.
    assert client.get(f"/press-reviews/{review_id}", headers=intrus).status_code == 404

    # 2) Modification par l'intrus. Un corps valide est fourni (titre et
    # contenu sont obligatoires), mais le 404 arrive avant la validation :
    # l'intrus n'apprend rien sur le contenu réel de la revue.
    assert client.patch(
        f"/press-reviews/{review_id}",
        headers=intrus,
        json={"title": "Volé", "content": "Contenu volé"},
    ).status_code == 404

    # 3) Suppression par l'intrus.
    assert client.delete(f"/press-reviews/{review_id}", headers=intrus).status_code == 404

    # La revue existe toujours et reste accessible à son propriétaire.
    assert client.get(f"/press-reviews/{review_id}", headers=owner).status_code == 200
