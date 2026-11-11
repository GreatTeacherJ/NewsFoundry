# NewsFoundry — Documentation complète de l'application

> Document rédigé à partir du code source au **10 novembre 2026**.
> Il décrit le fonctionnement réel de l'application, y compris les écarts avec le `README.md` et les limites connues.
> Les chemins cités sont relatifs à la racine du dépôt.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Stack technique et arborescence](#2-stack-technique-et-arborescence)
3. [Configuration](#3-configuration)
4. [Démarrage local](#4-démarrage-local)
5. [Architecture générale](#5-architecture-générale)
6. [Authentification et isolation des données](#6-authentification-et-isolation-des-données)
7. [Modèle de données](#7-modèle-de-données)
8. [Cycle de vie d'une discussion](#8-cycle-de-vie-dune-discussion)
9. [Fonctionnement détaillé du chat](#9-fonctionnement-détaillé-du-chat)
10. [Enregistrement des messages](#10-enregistrement-des-messages)
11. [Sources par discussion](#11-sources-par-discussion)
12. [Revues de presse](#12-revues-de-presse)
13. [Référence API](#13-référence-api)
14. [Frontend](#14-frontend)
15. [Prompts et comportement du modèle](#15-prompts-et-comportement-du-modèle)
16. [Fichiers annexes et code expérimental](#16-fichiers-annexes-et-code-expérimental)
17. [Limites connues et points d'attention](#17-limites-connues-et-points-dattention)
18. [Tests et vérifications](#18-tests-et-vérifications)
19. [Glossaire](#19-glossaire)

---

## 1. Vue d'ensemble

**NewsFoundry** est un assistant de veille et de synthèse d'actualité destiné aux journalistes et aux médias.
L'utilisateur discute avec un agent IA, qui peut interroger l'API **WorldNewsAPI** pour récupérer des articles, puis produire :

- une **réponse d'assistant** classique (explication, clarification, aperçu de l'actualité) ;
- une **revue de presse** rédigée selon un format imposé.

Les conversations, les messages, les sources récupérées et les revues de presse sont persistés en base de données et rattachés à l'utilisateur authentifié.

### Fonctionnalités réellement implémentées

| Fonctionnalité | État |
| --- | --- |
| Inscription / connexion e-mail + mot de passe | ✅ |
| JWT stocké dans un cookie `httpOnly` côté Next.js | ✅ |
| Discussions privées par utilisateur | ✅ |
| Messages utilisateur / assistant / revue en base | ✅ |
| Agent IA via PydanticAI + Mammouth (API compatible OpenAI) | ✅ |
| Récupération d'actualités via WorldNewsAPI (`top-news`, `search-news`) | ✅ |
| Sources enregistrées par discussion et réinjectées dans le prompt | ✅ |
| Génération d'une revue de presse à partir du dernier message `reviews` | ✅ |
| Consultation des revues dans une bibliothèque | ✅ |
| Édition / suppression des revues | API ✅, interface ❌ |
| Streaming de la réponse | ❌ (fichier expérimental séparé, non branché) |
| Affichage des sources dans l'interface | ❌ |
| Tests backend à jour avec l'intégration IA | ❌ (voir §18) |

> ⚠️ Le `README.md` indique encore que l'IA, PydanticAI et WorldNewsAPI « restent à intégrer ». Ce n'est plus exact : `backend/src/lib/callModele.py` les utilise réellement. Ce document décrit le code actuel.

---

## 2. Stack technique et arborescence

### Backend

- Python 3.13+, `uv`
- FastAPI + Uvicorn
- SQLModel / SQLAlchemy
- PostgreSQL en local/production (SQLite possible en développement et dans les tests)
- `bcrypt` pour les mots de passe, `PyJWT` pour les jetons
- `pydantic-ai` avec `OpenAIChatModel` pointant vers `https://api.mammouth.ai/v1`
- `requests` pour WorldNewsAPI
- `python-dotenv` pour charger `backend/.env`

### Frontend

- Next.js 16 (App Router), React 19, TypeScript strict
- `react-markdown` + `remark-gfm` pour afficher le Markdown des messages et revues
- Cookie `httpOnly` + Server Actions Next.js pour conserver le JWT côté serveur

### Arborescence utile

```text
P14DevIA/
├── AGENTS.md
├── README.md
├── docs/
│   ├── ai-quality.md
│   └── application.md            ← ce document
├── backend/
│   ├── .env / .env.example
│   ├── pyproject.toml
│   ├── conversation.txt          ← fichier de debug généré en cas d'échec IA
│   ├── src/
│   │   ├── main.py               ← application FastAPI, CORS, routers
│   │   ├── database.py           ← engine SQLModel, init_db()
│   │   ├── models.py             ← User, Discussion, Message, Source, PressReview
│   │   ├── pydanti_agent.py      ← exemple/expérimentation, non branché
│   │   ├── lib/
│   │   │   ├── callModele.py     ← agent, boucle news, appels WorldNewsAPI
│   │   │   └── prompt_systeme.py ← prompts système
│   │   └── routers/
│   │       ├── base.py           ← auth, discussions, messages, revues
│   │       └── chat.py           ← route stub /chats, non utilisée par le front
│   └── tests/test_api.py
└── frontend/
    ├── .env.local
    └── src/
        ├── app/
        │   ├── page.tsx          ← connexion (/)
        │   ├── home/page.tsx     ← nouvelle discussion (/home)
        │   ├── chat/[id]/page.tsx← discussion existante
        │   └── reviews/page.tsx  ← bibliothèque de revues
        ├── components/
        │   ├── AppShell.tsx      ← sidebar + historique
        │   ├── ChatView.tsx      ← chat
        │   ├── LoginForm.tsx
        │   ├── Header.tsx
        │   ├── ReviewsView.tsx
        │   ├── ReviewModal.tsx
        │   └── GenerateReviewModal.tsx
        ├── lib/
        │   ├── api.ts            ← appels API côté serveur (Server Action)
        │   ├── exportApi.ts      ← jsonBody, ApiError
        │   └── loginActions.ts   ← login/logout, cookie
        ├── types/typeApi.ts
        └── proxy.ts              ← protection des routes
```

---

## 3. Configuration

### Variables d'environnement backend (`backend/.env`)

| Variable | Rôle | Valeur par défaut |
| --- | --- | --- |
| `DATABASE_URL` | Connexion SQLAlchemy | `sqlite:///./newsfoundry.db` |
| `JWT_SECRET_KEY` | Clé de signature HS256 | vide → auth indisponible (`503`) |
| `JWT_ACCESS_TOKEN_MINUTES` | Durée du JWT | `480` (le `.env.example` met `60`) |
| `FRONTEND_ORIGINS` | Origines CORS, séparées par des virgules | `http://localhost:3000` |
| `API_KEY_WORLD` | Clé WorldNewsAPI | vide |
| `MAMMOUTH_KEY` | Clé de l'API Mammouth | vide |
| `AI_MODEL` | `test` → `TestModel` PydanticAI ; toute autre valeur → Mammouth | `test` |

`backend/src/lib/callModele.py` appelle `load_dotenv()` à l'import : le fichier `.env` est donc chargé même quand l'application est lancée sans `--env-file`.
Conséquence importante : les tests qui importent `routers.base` chargent aussi ce `.env`, donc `AI_MODEL` et les clés réelles peuvent être utilisés (voir §18).

### Variables d'environnement frontend (`frontend/.env.local`)

| Variable | Rôle | Valeur par défaut |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | URL de base de l'API FastAPI | `http://localhost:8000` |

---

## 4. Démarrage local

```bash
# 1. Base PostgreSQL
docker run --name newsfoundry_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=newsfoundry \
  -p 5432:5432 -d postgres:17

# 2. Backend
cd backend
cp .env.example .env        # puis renseigner JWT_SECRET_KEY, API_KEY_WORLD, MAMMOUTH_KEY
uv sync
uv run --env-file .env src/main.py
# API : http://localhost:8000 — Swagger : http://localhost:8000/docs

# 3. Frontend
cd frontend
npm ci
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
# Interface : http://localhost:3000
```

La création des tables se fait via `init_db()` dans `backend/src/database.py`, appelée uniquement dans le bloc `if __name__ == "__main__"` de `main.py`.

---

## 5. Architecture générale

```text
Navigateur
   │  (React / Next.js, cookie httpOnly "token")
   ▼
Next.js Server Actions (frontend/src/lib/api.ts)
   │  fetch + Authorization: Bearer <JWT>
   ▼
FastAPI (backend/src/main.py)
   ├── routers/base.py ──► SQLModel ──► PostgreSQL
   │        │
   │        └── lib/callModele.py
   │                ├── PydanticAI Agent ──► Mammouth (LLM)
   │                └── requests ─────────► WorldNewsAPI
   └── routers/chat.py (stub non utilisé)
```

Points clés :

- Le navigateur **ne voit jamais le JWT** : il est dans un cookie `httpOnly`, et les appels à l'API partent du serveur Next.js via des Server Actions (`"use server"` dans `frontend/src/lib/api.ts`).
- Le backend ne fait aucune mise en cache : le frontend envoie `cache: "no-store"`.
- Toutes les routes métier sont protégées par `get_current_user` et filtrées par propriétaire.

---

## 6. Authentification et isolation des données

### Inscription

`POST /auth/register` :

1. normalise l'e-mail en minuscules (`Credentials.normalize_email`) ;
2. vérifie l'unicité ;
3. hache le mot de passe avec `bcrypt.hashpw` ;
4. crée `User` et renvoie `{id, email}`.

Contraintes : mot de passe de 8 à 72 caractères et ≤ 72 octets (limite bcrypt), e-mail validé par `EmailStr`.

### Connexion

`POST /auth/login` :

1. retrouve l'utilisateur par e-mail ;
2. compare le mot de passe avec `bcrypt.checkpw` ;
3. si `JWT_SECRET_KEY` est vide → `503` ;
4. renvoie un JWT signé HS256 contenant :
   - `sub` : identifiant de l'utilisateur (chaîne) ;
   - `exp` : date d'expiration (`JWT_ACCESS_TOKEN_MINUTES`).

### Côté Next.js

1. `loginAction` (Server Action) appelle `/auth/login`, récupère `access_token` et pose un cookie :
   - `httpOnly`, `sameSite=lax`, `secure` en production, `maxAge = 8 h`, `path=/`.
2. `frontend/src/proxy.ts` (middleware) :
   - route publique : `/` uniquement ;
   - sans cookie sur une route protégée → redirection vers `/` ;
   - avec cookie sur `/` → redirection vers `/home`.
3. `api()` lit le cookie et ajoute `Authorization: Bearer <token>`. Les routes `/auth/register` et `/auth/login` sont appelées sans jeton.
4. `logoutAction` supprime le cookie et redirige vers `/login` (route qui n'existe pas ; le middleware renvoie ensuite vers `/`).

### Isolation

- Chaque discussion possède `owner_id`.
- `get_owned_discussion()` exige `id` **et** `owner_id` : une ressource d'un autre utilisateur renvoie **404**, pas 403, pour ne pas révéler son existence.
- Les messages sont accessibles uniquement après vérification de la discussion parente.
- Les revues sont filtrées par `PressReview.owner_id`.
- Les sources n'ont pas de route publique : elles sont accessibles uniquement via leur `discussion_id`, donc indirectement protégées.

---

## 7. Modèle de données

Défini dans `backend/src/models.py` (SQLModel). Les noms de tables sont les noms de classes en minuscules : `user`, `discussion`, `message`, `source`, `press_review`.

### `User`

| Champ | Type | Contraintes |
| --- | --- | --- |
| `id` | int | PK |
| `email` | str | unique, indexé, max 320 |
| `hashed_password` | str | bcrypt |
| `created_at` | datetime | UTC par défaut |

### `Discussion`

| Champ | Type | Contraintes |
| --- | --- | --- |
| `id` | int | PK |
| `owner_id` | int | FK `user.id`, indexé |
| `title` | str | défaut « Nouvelle discussion », max 200 |
| `created_at` | datetime | UTC |
| `updated_at` | datetime | UTC, mis à jour à chaque message et renommage |

### `Message`

| Champ | Type | Contraintes |
| --- | --- | --- |
| `id` | int | PK |
| `discussion_id` | int | FK `discussion.id`, indexé |
| `role` | str | max 20 : `user`, `assistant` ou `reviews` |
| `content` | str | texte libre (max 20 000 via l'API) |
| `created_at` | datetime | UTC |

### `Source`

| Champ | Type | Contraintes |
| --- | --- | --- |
| `id` | int | PK |
| `discussion_id` | int | FK `discussion.id`, indexé |
| `content` | str | JSON brut renvoyé par WorldNewsAPI |
| `created_at` | datetime | UTC |

### `PressReview`

| Champ | Type | Contraintes |
| --- | --- | --- |
| `id` | int | PK |
| `owner_id` | int | FK `user.id`, indexé |
| `discussion_id` | int | FK `discussion.id`, indexé |
| `title` | str | max 200 |
| `content` | str | texte Markdown |
| `created_at` | datetime | UTC |

### Relations

```text
User 1 ──── n Discussion 1 ──── n Message
  │              │
  │              ├──────────── n Source
  │              │
  │              └──────────── n PressReview
  │
  └──────────── n PressReview
```

Remarques :

- Aucune relation SQLAlchemy `relationship()` n'est déclarée : les jointures sont faites manuellement avec `select(...).where(...)`.
- Aucune contrainte `ON DELETE CASCADE` : les suppressions sont faites à la main.
- `Source` n'a pas de propriétaire direct ; l'accès passe par la discussion.

---

## 8. Cycle de vie d'une discussion

1. **Création** : `POST /discussions` avec un titre (1–200 caractères). Si le titre est vide après `strip()` → `422`.
2. **Premier message depuis `/home`** : le front crée la discussion avec les 80 premiers caractères du message comme titre, puis redirige vers `/chat/{id}`.
3. **Ajout de messages** : chaque `POST /discussions/{id}/messages` enregistre le message utilisateur, la réponse IA et éventuellement de nouvelles sources, puis met à jour `updated_at`.
4. **Renommage** : `PATCH /discussions/{id}` met à jour le titre et `updated_at`.
5. **Suppression** : `DELETE /discussions/{id}` supprime dans l'ordre les messages, les revues, puis la discussion.
   - ⚠️ Les **sources ne sont pas supprimées** : elles deviennent orphelines (voir §17).
6. **Historique** : `AppShell` recharge `GET /discussions` à chaque changement de route et les trie par `updated_at` décroissant.

---

## 9. Fonctionnement détaillé du chat

C'est le cœur de l'application. Le parcours va du formulaire React jusqu'à la base de données, en passant par l'agent et WorldNewsAPI.

### 9.1 Côté navigateur (`frontend/src/components/ChatView.tsx`)

- `discussionId` est fourni par la route `/chat/[id]` ; sur `/home`, il est absent.
- Au chargement d'une discussion existante, deux appels sont faits en parallèle :
  ```ts
  api<Discussion>(`/discussions/${discussionId}`)
  api<Message[]>(`/discussions/${discussionId}/messages`)
  ```
- `sendMessage(event)` :
  1. refuse un message vide ou un envoi pendant qu'une requête est en cours (`busy`) ;
  2. vide immédiatement le champ ;
  3. si aucune discussion n'existe, crée `POST /discussions` avec `title = message.slice(0, 80)` ;
  4. envoie `POST /discussions/{id}/messages` avec `{ content }` ;
  5. reçoit un tableau `[messageUtilisateur, messageAssistant]` ;
  6. ajoute les deux messages à l'état local et redirige vers `/chat/{id}` si nécessaire ;
  7. en cas d'erreur, affiche le `detail` renvoyé par l'API.
- Le bouton « Générer une revue de presse » reste toujours cliquable ; la vérification de la présence d'un message `reviews` est faite au moment du clic, dans `generateReview`.
- Les messages sont rendus en Markdown avec `react-markdown` + `remark-gfm` et reçoivent une classe CSS différente selon `role` (`user`, `assistant`, `reviews`).

### 9.2 Traitement backend (`backend/src/routers/base.py`, `create_message`)

Étapes exactes :

1. `get_owned_discussion(session, discussion_id, user.id)` → `404` si la discussion n'existe pas ou appartient à un autre utilisateur.
2. `content = payload.content.strip()` → `422` si vide.
3. Construction d'un objet `Message(role="user")` **pas encore ajouté à la session**.
4. Chargement de l'historique existant :
   ```python
   db_messages = select(Message)
       .where(Message.discussion_id == discussion_id)
       .order_by(Message.created_at, Message.id)
   ```
   ⚠️ Le message courant n'est **pas** inclus dans `db_messages` ; il est transmis séparément comme `prompt`.
5. Chargement de **toutes les sources** de la discussion :
   ```python
   db_sources = select(Source)
       .where(Source.discussion_id == discussion_id)
       .order_by(Source.created_at)
   ```
6. Appel :
   ```python
   response_ai, source_ai = call_modele_chat(content, db_messages, db_sources)
   ```
7. Création du message assistant avec `role = response_ai.kind`
   (`"assistant"` ou `"reviews"`).
8. Si `source_ai` n'est pas vide, création d'une ligne `Source` **par entrée**.
9. `discussion.updated_at = utc_now()`.
10. Ajout et `commit()` de la source éventuelle, du message utilisateur, du message assistant et de la discussion.
11. `refresh()` des deux messages puis retour `[message, assistant]` (`201`).

Tout est fait dans une seule transaction : si le commit échoue, rien n'est persisté.

### 9.3 Appel de l'agent (`backend/src/lib/callModele.py`)

Le module choisit le modèle au chargement :

```python
MODEL_NAME = os.getenv("AI_MODEL", "test")
model = TestModel(custom_output_args={"kind": "reviews", "content": review}) \
        if MODEL_NAME == "test" else MAMMOUTH
```

- `TestModel` : aucun appel réseau, renvoie la revue d'exemple codée en dur (`review`).
- `MAMMOUTH` : `OpenAIChatModel("mammouth-recommended", provider=OpenAIProvider(base_url="https://api.mammouth.ai/v1", api_key=MAMMOUTH_KEY))`.

Deux agents sont définis :

- `chat_agent` : prompt système `PROMPT_SYSTEME_BASE`, sortie typée `ResModel | NeedTopNews | NeedSearchNews` ;
- `chat_agent_2` : sortie `NeedTopNews | NeedSearchNews` (déclaré mais non utilisé dans la boucle).

Types de sortie :

```python
class ResModel(BaseModel):
    kind: Literal["reviews", "assistant"]
    content: str

class NeedTopNews(BaseModel):
    kind: Literal["top-news"] = "top-news"
    parametres: ParamsTopNews

class NeedSearchNews(BaseModel):
    kind: Literal["search-news"] = "search-news"
    parametres: ParamsSearchNews
```

### 9.4 Conversion de l'historique

`to_pydantic_history(db_messages)` transforme les lignes SQL en messages PydanticAI :

| `Message.role` en base | Type PydanticAI |
| --- | --- |
| `user` | `ModelRequest(parts=[UserPromptPart(...)])` |
| `assistant` | `ModelResponse(parts=[TextPart(...)])` |
| `reviews` | `ModelResponse(parts=[TextPart(...)])` |

Autrement dit, une revue déjà générée est rejouée au modèle comme une réponse d'assistant.

### 9.5 Boucle de récupération d'actualités

`call_modele_chat(prompt, db_messages, db_source)` :

1. Construit l'historique PydanticAI.
2. Récupère le texte de chaque source via `_source_text` :
   - `Source` → `source.content` (JSON stocké) ;
   - `dict` → `json.dumps(...)` ;
   - `str` → tel quel.
3. Si des sources existent, les ajoute au prompt :
   ```text
   <message utilisateur>

   Données déjà récupérées :
   <source 1>
   <source 2>
   ```
   C'est ainsi que les sources des tours précédents sont réutilisées : **elles sont injectées dans le prompt de l'utilisateur**, pas dans le prompt système.
4. Boucle `for _ in range(MAX_NEWS_ROUNDS)` avec `MAX_NEWS_ROUNDS = 3` :
   1. `chat_agent.run_sync(user_prompt=followup, message_history=history)` ;
   2. `history = run.all_messages()` pour conserver l'échange complet ;
   3. selon la sortie :
      - `NeedTopNews` ou `NeedSearchNews` → `call_world_new(result)` ;
        - la réponse JSON est ajoutée à `new_sources` ;
        - un nouveau `followup` demande au modèle de conclure sans rappeler l'API ;
        - la boucle continue ;
      - `ResModel` → retour immédiat `(result, new_sources)`.
5. Si les 3 tours sont épuisés sans `ResModel` :
   - le transcript complet est écrit dans `backend/conversation.txt` (ou dans le répertoire courant du processus) ;
   - `RuntimeError("Trop de demandes de news successives")` est levée.

> Le commentaire du prompt système dit « un seul appel par demande », mais le code autorise jusqu'à 3 appels successifs. C'est la boucle qui fait foi.

### 9.6 Appel WorldNewsAPI

`call_world_new(result)` :

1. `result.parametres.model_dump(by_alias=True, exclude_none=True, mode="json")`
   → clés avec tirets (`source-country`, `headlines-only`), dates au format `AAAA-MM-JJ`, champs vides retirés.
2. Les booléens Python sont convertis en `"true"` / `"false"` (attendu par l'API).
3. URL :
   ```text
   https://api.worldnewsapi.com/{top-news|search-news}?<query>
   ```
4. Requête `GET` avec l'en-tête `x-api-key: <API_KEY_WORLD>` et un timeout de 50 s.
5. `raise_for_status()` puis retour de `res.json()`.

Paramètres possibles :

- **`top-news`** : `source-country` et `language` obligatoires ; `date`, `headlines-only`, `max-news-per-cluster` optionnels.
- **`search-news`** : `text`, `text-match-indexes`, `source-country`, `language`, `earliest-publish-date`, `latest-publish-date`, `categories`.

### 9.7 Exemple complet

Message : « Fais-moi une revue de presse sur l'IA en France. »

```text
1. Front        POST /discussions/12/messages {content: "..."}
2. Backend      charge la discussion, les messages précédents et les sources
3. call_modele  envoie le prompt + historique au LLM
4. LLM          répond NeedSearchNews {text: "intelligence artificielle",
                                        source-country: "fr", language: "fr"}
5. Backend      GET https://api.worldnewsapi.com/search-news?...
6. Backend      réinjecte le JSON obtenu dans le prompt
7. LLM          répond ResModel {kind: "reviews", content: "**REVUE DE PRESSE ..."}
8. Backend      enregistre :
                  - le message user
                  - le message assistant avec role = "reviews"
                  - une ligne Source contenant le JSON WorldNews
9. Front        affiche les deux messages ; le bouton de génération est actif
```

---

## 10. Enregistrement des messages

### Structure

Chaque message est une ligne de la table `message` :

```json
{
  "id": 42,
  "discussion_id": 12,
  "role": "assistant",
  "content": "**REVUE DE PRESSE ...**",
  "created_at": "2026-11-10T14:32:05.123456+00:00"
}
```

### Rôles

| `role` | Origine | Signification |
| --- | --- | --- |
| `user` | `create_message` | Message saisi par l'utilisateur |
| `assistant` | `response_ai.kind` | Réponse textuelle standard de l'IA |
| `reviews` | `response_ai.kind` | Revue de presse complète générée par l'IA |

Le rôle n'est pas choisi par le frontend : il vient directement du champ `kind` de la sortie structurée du modèle. Le type `ResModel` ne permet que `assistant` ou `reviews`.

### Ordre de lecture

L'historique est trié par `(created_at, id)` croissant. Le `id` sert de départage si deux messages ont le même horodatage.

### Contraintes

- `content` : 1 à 20 000 caractères via `MessageCreate` / `MessageUpdate`.
- `strip()` avant enregistrement ; un contenu vide → `422`.
- `role` : max 20 caractères en base, sans validation métier côté modèle.
- `created_at` : UTC, généré par `utc_now()`.

### Réponse de l'endpoint

`POST /discussions/{id}/messages` renvoie **deux messages** :

```json
[
  { "id": 41, "role": "user",    "content": "...", "discussion_id": 12, "created_at": "..." },
  { "id": 42, "role": "reviews", "content": "...", "discussion_id": 12, "created_at": "..." }
]
```

### Modification et suppression

- `PATCH /discussions/{id}/messages/{message_id}` : modifie uniquement le contenu d'un message appartenant à la discussion.
- `DELETE /discussions/{id}/messages/{message_id}` : supprime un message.
- Aucun recalcul de la réponse IA n'est déclenché.
- L'interface n'expose ni l'édition ni la suppression des messages.

### Différence avec `pydanti_agent.py`

Le fichier `backend/src/pydanti_agent.py` contient une autre implémentation de stockage (SQLite `messages(id, message_list)` avec des messages PydanticAI sérialisés). **Elle n'est pas utilisée** par l'application : le chat réel passe par `routers/base.py` et la table `message`.

---

## 11. Sources par discussion

### Définition

Une « source » est ici **la réponse JSON brute d'un appel WorldNewsAPI**, et non un article individuel normalisé.

Exemple simplifié de `Source.content` :

```json
{
  "status": "ok",
  "totalResults": 37,
  "news": [
    {
      "id": 123456,
      "title": "Titre de l'article",
      "text": "Contenu...",
      "url": "https://...",
      "publish_date": "2026-11-09 08:15:00",
      "source_country": "fr",
      "language": "fr"
    }
  ]
}
```

### Enregistrement

Dans `create_message` :

```python
if source_ai:
    for s in source_ai:
        session.add(Source(discussion_id=discussion.id, content=s))
```

- `source_ai` est la liste `new_sources` retournée par `call_modele_chat`.
- Une entrée est ajoutée **uniquement** lorsqu'un appel `top-news` ou `search-news` a réellement eu lieu pendant ce tour.
- Une réponse directe `assistant` ou `reviews` sans appel API n'ajoute aucune source.
- Chaque entrée correspond à **un appel API**, pas à un article.

### Utilisation

Lors de chaque nouveau message de la discussion :

1. toutes les sources de la discussion sont relues, triées par `created_at` ;
2. leur contenu est concaténé dans le prompt utilisateur sous « Données déjà récupérées : » ;
3. le modèle est invité par le prompt système à utiliser ces données avant de rappeler l'API ;
4. s'il rappelle l'API, la nouvelle réponse est ajoutée aux sources existantes.

Les sources sont donc **cumulatives et persistantes** pendant toute la durée de vie de la discussion.

### Portée et confidentialité

- Les sources sont liées à `discussion_id`, jamais à `user_id`.
- Aucune route API ne les expose ; elles ne sont pas renvoyées au frontend.
- L'isolation repose sur la vérification de la discussion propriétaire avant tout accès aux messages, et sur le fait qu'aucun endpoint ne lit `Source` directement.
- L'interface n'affiche jamais les sources : l'utilisateur voit seulement la synthèse et la ligne « Sources » éventuellement rédigée par le modèle.

### Limites

- **Accumulation non bornée** : chaque appel API ajoute un JSON potentiellement volumineux. Au fil d'une longue discussion, le prompt peut devenir très grand et dépasser la fenêtre du modèle ou augmenter fortement le coût.
- **Doublons possibles** : si le modèle rappelle l'API, les mêmes articles peuvent être stockés plusieurs fois.
- **Pas de normalisation** : les articles ne sont pas extraits dans une table dédiée (`title`, `url`, `publisher`, etc.), ce qui rend impossible une déduplication ou un affichage structuré sans retraitement.
- **Suppression** : `DELETE /discussions/{id}` supprime messages et revues, mais **pas les sources**. Elles restent en base et ne sont plus accessibles.
- **Pas de contrôle de fraîcheur** : aucune date d'expiration ; une source ancienne est réinjectée indéfiniment.

---

## 12. Revues de presse

Il faut distinguer deux objets :

| Objet | Table | Rôle |
| --- | --- | --- |
| Message `reviews` | `message` | Revue générée dans le fil de discussion |
| `PressReview` | `press_review` | Copie sauvegardée dans la bibliothèque de revues |

### 12.1 Génération de la revue dans le chat

La revue est produite par l'agent lui-même, lorsque sa sortie est `ResModel(kind="reviews", content=...)`.
Le prompt système impose un format strict (voir §15) :

```markdown
**REVUE DE PRESSE [THÈME] - [JJ Mois AAAA]**

**[Phrase d'introduction factuelle et neutre] :**

• **[Titre du sujet 1]** : [Résumé en 1 à 2 phrases].

• **[Titre du sujet 2]** : [Résumé].

• **[Titre du sujet 3]** : [Résumé].

**Sources** : [Média et date de publication de chaque article utilisé].
```

La réponse est enregistrée comme un `Message` avec `role = "reviews"`.
C'est ce message qui sert de matière première à la bibliothèque.

### 12.2 Sauvegarde dans la bibliothèque

Parcours utilisateur :

1. Dans une discussion, le bouton « Générer une revue de presse » ouvre `GenerateReviewModal`.
2. Le modal demande un « thème », mais **ce champ n'est pas relié à l'état React** (`onThemeChange` est un no-op et l'input n'a pas de `value`/`onChange`). Le thème saisi est ignoré.
3. Le clic sur « Générer » appelle `generateReview()` dans `ChatView.tsx` :
   - vérifie qu'au moins un message local a `role === "reviews"` ;
   - sinon affiche « Aucun revue trouvée. Demander au chat de vous en créer une. » et s'arrête ;
   - sinon `POST /discussions/{id}/press-reviews` ;
   - en cas de succès, redirige vers `/reviews`.
4. Côté backend, `create_press_review` :
   ```python
   discussion = get_owned_discussion(...)
   reviews_discussion = select(Message)
       .where(Message.discussion_id == discussion_id)
       .where(Message.role == "reviews")
       .order_by(Message.created_at.desc())
       .first()
   review = PressReview(
       owner_id=user.id,
       discussion_id=discussion.id,
       title=f"Revue de presse — {discussion.title}",
       content=reviews_discussion.content,
   )
   ```
   - sélectionne le **dernier** message `reviews` de la discussion ;
   - copie son contenu dans une nouvelle `PressReview` ;
   - génère automatiquement le titre à partir du titre de la discussion ;
   - renvoie `201` avec la revue créée.

**La revue sauvegardée est un instantané indépendant.** Modifier la discussion ou les messages ensuite ne change pas la `PressReview`.

### 12.3 Cas d'erreur

- Si aucun message `reviews` n'existe, `reviews_discussion` vaut `None` et `reviews_discussion.content` lève `AttributeError` → **500**. Le garde-fou existe uniquement dans le frontend, pas dans l'API.
- Si la discussion appartient à un autre utilisateur → `404`.
- Aucun contrôle sur la présence réelle de sources ou sur la validité éditoriale de la revue.

### 12.4 Consultation

`GET /press-reviews` renvoie toutes les revues de l'utilisateur, triées par `created_at` décroissant.

`ReviewsView.tsx` :

- affiche chaque revue sous forme de carte ;
- rend le contenu en Markdown ;
- affiche un badge **« Politique » codé en dur** (aucune catégorie n'est stockée) ;
- ouvre `ReviewModal` pour la lecture complète ;
- permet de **copier** le contenu dans le presse-papiers.

L'API permet aussi `GET`, `PATCH` et `DELETE` sur `/press-reviews/{id}`, mais **aucun bouton d'édition ou de suppression** n'existe dans l'interface.

---

## 13. Référence API

Base : `http://localhost:8000` — documentation interactive : `/docs`.

| Méthode | Route | Auth | Corps | Réponse |
| --- | --- | --- | --- | --- |
| `GET` | `/` | non | — | message de santé |
| `POST` | `/auth/register` | non | `{email, password}` | `201 {id, email}` |
| `POST` | `/auth/login` | non | `{email, password}` | `{access_token, token_type}` |
| `GET` | `/auth/me` | oui | — | `{id, email}` |
| `GET` | `/discussions` | oui | — | liste triée par `updated_at` desc |
| `POST` | `/discussions` | oui | `{title?}` | `201 Discussion` |
| `GET` | `/discussions/{id}` | oui | — | `Discussion` |
| `PATCH` | `/discussions/{id}` | oui | `{title}` | `Discussion` |
| `DELETE` | `/discussions/{id}` | oui | — | `204` |
| `GET` | `/discussions/{id}/messages` | oui | — | liste triée par `created_at`, `id` |
| `POST` | `/discussions/{id}/messages` | oui | `{content}` | `201 [userMessage, assistantMessage]` |
| `PATCH` | `/discussions/{id}/messages/{message_id}` | oui | `{content}` | `Message` |
| `DELETE` | `/discussions/{id}/messages/{message_id}` | oui | — | `204` |
| `POST` | `/discussions/{id}/press-reviews` | oui | — | `201 PressReview` |
| `GET` | `/press-reviews` | oui | — | liste triée par `created_at` desc |
| `GET` | `/press-reviews/{id}` | oui | — | `PressReview` |
| `PATCH` | `/press-reviews/{id}` | oui | `{title, content}` | `PressReview` |
| `DELETE` | `/press-reviews/{id}` | oui | — | `204` |
| `POST` | `/chats` | non | paramètre `prompt` | `{"content": "message reçu"}` (stub) |

Codes d'erreur notables :

- `401` : jeton absent, invalide ou expiré ; identifiants incorrects.
- `404` : ressource inexistante **ou appartenant à un autre utilisateur**.
- `409` : e-mail déjà utilisé (`IntegrityError` ou vérification préalable).
- `422` : validation Pydantic, titre/message/contenu vide.
- `503` : `JWT_SECRET_KEY` non configurée.

`routers/chat.py` est un stub de démonstration (`POST /chats`) non utilisé par le frontend.

---

## 14. Frontend

### Routes

| Route | Fichier | Contenu |
| --- | --- | --- |
| `/` | `app/page.tsx` | `LoginForm` : connexion ou création de compte |
| `/home` | `app/home/page.tsx` | `AppShell` + `Header` + `ChatView` sans `discussionId` |
| `/chat/[id]` | `app/chat/[id]/page.tsx` | `AppShell` + `ChatView` avec `discussionId` |
| `/reviews` | `app/reviews/page.tsx` | `AppShell` + `Header` + `ReviewsView` |

`/login` n'existe pas ; `logoutAction` redirige vers `/login`, puis le middleware renvoie vers `/`.

### Composants

- **`AppShell`** : sidebar avec logo, historique des discussions (`GET /discussions`), bouton de déconnexion. Recharge l'historique à chaque changement de `pathname`.
- **`ChatView`** : chargement de la discussion, envoi de message, création implicite de discussion, affichage Markdown, bouton et modal de revue.
- **`Header`** : navigation Chat / Revue de presse avec état actif.
- **`ReviewsView`** : chargement de `GET /press-reviews`, cartes et modal de lecture.
- **`ReviewModal`** : lecture plein écran, copie, fermeture par `Échap` ou clic sur le fond.
- **`GenerateReviewModal`** : confirmation de génération (thème non fonctionnel).
- **`LoginForm`** : bascule connexion / inscription, puis `loginAction`.

### Couche réseau

`frontend/src/lib/api.ts` :

- marqué `"use server"` : les fonctions exportées sont des **Server Actions** exécutées côté serveur Next.js, même lorsqu'elles sont appelées depuis un composant client ;
- lit le cookie `token` sauf pour `/auth/register` et `/auth/login` ;
- ajoute `Authorization: Bearer <token>` ;
- ajoute `Content-Type: application/json` uniquement s'il y a un corps ;
- `cache: "no-store"` ;
- convertit les erreurs en `ApiError(message, status)` ;
- gère `204` en renvoyant `undefined`.

Cela explique pourquoi le JWT peut rester `httpOnly` : il n'est jamais lu par du JavaScript navigateur.

### Rendu Markdown

Les messages et les revues sont affichés avec :

```tsx
<ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
```

Les tableaux, listes, gras, liens et titres générés par le modèle sont donc interprétés.

---

## 15. Prompts et comportement du modèle

Fichier : `backend/src/lib/prompt_systeme.py`.

Deux prompts sont définis :

- **`PROMPT_SYSTEME_BASE`** : utilisé par `chat_agent`. Il décrit :
  - le rôle d'assistant de revue de presse ;
  - la langue de réponse (celle de l'utilisateur) ;
  - le périmètre (actualité, presse, déontologie) ;
  - les trois types de sortie : `assistant`, `reviews`, `top-news` / `search-news` ;
  - les règles d'appel WorldNewsAPI et les paramètres ;
  - le format strict de la revue de presse ;
  - le style (neutre, factuel).
- **`PROMPT_SYSTEME_WITH_NEWS`** : variante prévue pour des actualités fournies directement dans la requête. **Il n'est pas utilisé** par le code actuel.

Points importants :

- Le prompt interdit d'inventer des faits et demande de s'appuyer uniquement sur les données reçues.
- Il impose un seul type de sortie par tour.
- Il demande de ne pas rappeler l'API si les données sont déjà présentes.
- Le placeholder `[DATE_DU_JOUR]` n'est **pas remplacé dynamiquement** : le modèle ne reçoit pas la date courante injectée par le code.
- La revue doit contenir une section `**Sources**` citant média et date.

---

## 16. Fichiers annexes et code expérimental

### `backend/src/pydanti_agent.py`

Exemple complet d'application de chat PydanticAI :

- agent + streaming ;
- base SQLite `.chat_app_messages.sqlite` ;
- routes `/`, `/chat_app.ts`, `/chat/` ;
- stockage des messages PydanticAI sérialisés.

Ce fichier **n'est importé nulle part** dans l'application réelle. Il contient aussi une clé API en clair (`api_key='...'`) et un modèle `mon-modele`. Il ne doit pas être confondu avec le chat de NewsFoundry.

### `backend/conversation.txt`

Fichier de debug écrit par `call_modele_chat` **uniquement** lorsque `MAX_NEWS_ROUNDS` est dépassé. Il contient le transcript complet de la boucle (prompt, sorties de l'agent, réponses API). Il est généré dans le répertoire courant du processus, souvent `backend/`.

### `backend/src/routers/chat.py`

Stub :

```python
@router.post("/chats")
def chat_completion(prompt: str):
    return {"content": "message reçu"}
```

Non utilisé par le frontend et sans authentification.

---

## 17. Limites connues et points d'attention

Cette section liste les écarts, bugs potentiels et dette technique observés dans le code actuel.

### Bugs et fragilités

1. **Création de revue sans message `reviews`** → `AttributeError` et `500`.
   Le backend devrait vérifier `reviews_discussion is None` et renvoyer `404` ou `422`.

2. **Sources orphelines** à la suppression d'une discussion.
   `delete_discussion` supprime messages et revues, pas les `Source`.

3. **Champ « thème » du modal non fonctionnel**.
   `GenerateReviewModal` affiche un input mais ne le relie à aucun état ; le thème est ignoré et le titre vient de la discussion.

4. **Badge « Politique » codé en dur** dans `ReviewsView`, alors qu'aucune catégorie n'est stockée.

5. **Tests backend désynchronisés** : `test_discussion_messages_and_press_review_lifecycle` attend encore les réponses de démonstration (« aucune IA », « en attente ») alors que l'IA et WorldNewsAPI sont branchées.

6. **Tests dépendants du réseau et du `.env`** : `load_dotenv()` dans `callModele.py` charge les vraies clés à l'import ; sans mock, les tests peuvent appeler Mammouth et WorldNewsAPI.

7. **`[DATE_DU_JOUR]` non injecté** dans le prompt système.

8. **`PROMPT_SYSTEME_WITH_NEWS` mort** : défini mais jamais utilisé.

9. **Pas de streaming** dans l'application réelle : la réponse complète est attendue avant l'enregistrement et l'affichage.

10. **Pas de limite de taille des sources** : le prompt peut croître indéfiniment.

11. **Pas de déduplication des sources** : les mêmes articles peuvent être stockés plusieurs fois.

12. **`role` non validé en base** : une sortie inattendue du modèle pourrait écrire une valeur arbitraire (limitée à 20 caractères).

13. **Pas de retry ni de gestion fine des erreurs WorldNewsAPI** : un échec HTTP lève une exception et remonte en `500`.

14. **`call_world_new` utilise `requests` synchrone** dans une route FastAPI synchrone : cela bloque le worker pendant l'appel (timeout 50 s).

15. **Le frontend ne recharge pas la discussion après génération** : il pousse les deux messages renvoyés, ce qui est cohérent, mais un rechargement de page est nécessaire pour voir d'éventuelles sources (qui ne sont de toute façon pas affichées).

16. **Aucune pagination** sur les discussions ni les revues.

17. **Pas de rate limiting, pas de réinitialisation de mot de passe, pas de vérification d'e-mail.**

18. **`backend/src/pydanti_agent.py` contient une clé API en dur** (valeur `'...'`, mais le motif est à proscrire) et n'est pas utilisé.

### Incohérences de documentation

- Le `README.md` et `docs/ai-quality.md` affirment que l'IA et WorldNewsAPI ne sont pas intégrées : c'est faux depuis l'ajout de `callModele.py`.
- Le `README` mentionne `uv sync --locked` en CI, `JWT_ACCESS_TOKEN_MINUTES=60` dans `.env.example`, mais le code a une valeur par défaut de `480`.

### Pistes d'amélioration prioritaires

1. Corriger le garde-fou `reviews_discussion is None`.
2. Supprimer les sources avec la discussion, ou ajouter `ON DELETE CASCADE`.
3. Normaliser les articles dans une table `Article` (titre, URL, média, date) au lieu de stocker le JSON brut.
4. Borner et dédupliquer les sources injectées (fenêtre temporelle, nombre max, hash).
5. Brancher le champ « thème » ou le retirer du modal.
6. Mocker `call_modele_chat` dans les tests et mettre à jour les assertions.
7. Injecter la date du jour dans le prompt.
8. Ajouter l'édition/suppression des revues dans l'interface.
9. Rendre les appels WorldNewsAPI asynchrones (`httpx.AsyncClient`) avec timeout et retry bornés.
10. Ajouter un streaming SSE pour l'expérience utilisateur.

---

## 18. Tests et vérifications

### Backend

```bash
cd backend
uv run pytest -q
uv run ruff check src tests
```

Les tests utilisent une base SQLite en mémoire (`StaticPool`) et remplacent `get_session` par une dépendance de test. `JWT_SECRET_KEY` est défini dans `tests/test_api.py`.

Couverture actuelle :

- inscription, connexion, mauvais mot de passe, doublon d'e-mail ;
- cycle discussion → messages → revue → suppression ;
- isolation entre deux utilisateurs ;
- rejet des requêtes non authentifiées et des jetons invalides.

**État au 10/11/2026** : `1 failed, 3 passed`.
Le test `test_discussion_messages_and_press_review_lifecycle` échoue car il attend `"aucune IA"` alors que le modèle réel (chargé depuis `.env`) a répondu par une vraie synthèse. La cause est l'absence de mock de `call_modele_chat` et la présence de `load_dotenv()`.

Pour corriger durablement :

```python
# dans les tests, avant l'appel
monkeypatch.setattr(
    base,
    "call_modele_chat",
    lambda prompt, messages, sources: (ResModel(kind="assistant", content="Réponse de test"), []),
)
```

ou forcer un modèle de test et adapter les assertions au nouveau comportement.

### Frontend

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Le build doit conserver `--webpack` (déjà présent dans `package.json`).

---

## 19. Glossaire

| Terme | Définition |
| --- | --- |
| **Discussion** | Fil de conversation appartenant à un utilisateur. |
| **Message** | Tour de parole (`user`, `assistant` ou `reviews`) dans une discussion. |
| **Source** | Réponse JSON brute d'un appel WorldNewsAPI, liée à une discussion. |
| **Revue de presse (message)** | Message de rôle `reviews` généré par l'IA dans le fil. |
| **Revue de presse (bibliothèque)** | `PressReview` : copie indépendante d'un message `reviews`, consultable dans `/reviews`. |
| **`kind`** | Champ de sortie structurée du modèle : `assistant`, `reviews`, `top-news` ou `search-news`. |
| **WorldNewsAPI** | Service externe fournissant `top-news` et `search-news`. |
| **Mammouth** | Fournisseur LLM compatible OpenAI, utilisé via PydanticAI. |
| **PydanticAI** | Framework d'agents typés utilisé pour piloter le modèle et valider les sorties. |
| **JWT** | Jeton signé HS256 identifiant l'utilisateur, stocké dans un cookie `httpOnly`. |

---

*Fin du document.*
