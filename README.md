# NewsFoundry

Assistant de veille et de synthèse d'actualité destiné aux médias et aux journalistes. L'utilisateur dialogue avec une IA qui va chercher des articles réels (World News API), les résume et peut produire une **revue de presse** enregistrable dans une bibliothèque personnelle.

## Fonctionnalités

- Inscription et connexion par email / mot de passe (JWT).
- Discussions avec un assistant IA (PydanticAI, modèle servi par Mammouth AI).
- Récupération d'articles en direct via [World News API](https://worldnewsapi.com/) (`top-news` et `search-news`), décidée par le modèle lui-même.
- Les articles récupérés sont stockés en base et réutilisés dans la suite de la discussion (« pseudo RAG »).
- Génération, consultation, modification et suppression de revues de presse.
- Isolation stricte des données par utilisateur : une ressource d'un autre compte renvoie `404`.

## Architecture

```text
┌────────────────────┐   Server Actions    ┌──────────────────────┐        ┌──────────────┐
│ Frontend Next.js   │ ──────────────────► │ Backend FastAPI      │ ─────► │ PostgreSQL   │
│ (React 19, :3000)  │  Bearer <JWT>       │ (:8000)              │        └──────────────┘
│ cookie httpOnly    │ ◄────────────────── │  └─ PydanticAI Agent │ ─────► Mammouth AI (LLM)
└────────────────────┘                     │                      │ ─────► World News API
                                           └──────────────────────┘
```

| Dossier | Contenu | Documentation |
| --- | --- | --- |
| [`backend/`](backend/README.md) | API FastAPI, base de données SQLModel, agent IA | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend/README.md) | Interface Next.js (connexion, chat, revues) | [frontend/README.md](frontend/README.md) |
| [`docs/`](docs/ai-quality.md) | Protocole d'évaluation de la qualité IA | [docs/ai-quality.md](docs/ai-quality.md) |
| [`docs/`](docs/optimisation-tokens-llm.md) | Proposition d'amélioration| [docs/optimisation-tokens-llm.md](docs/optimisation-tokens-llm.md) |

Les deux projets sont indépendants : il n'y a pas de lanceur à la racine, chaque commande se lance depuis `backend/` ou `frontend/`.

## Prérequis

- Python 3.13+ et [`uv`](https://docs.astral.sh/uv/)
- Node.js 22 et npm
- Docker (pour PostgreSQL en local)
- Pour l'IA réelle : une clé Mammouth AI et une clé World News API (inutiles en mode test, voir plus bas)

## Démarrage rapide

### 1. Backend

```bash
cd backend
cp .env.example .env      # puis renseigner JWT_SECRET_KEY et les clés API
uv sync

docker run --name newsfoundry_db \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=newsfoundry \
  -p 5432:5432 -d postgres:17

uv run --env-file .env src/main.py
```

L'API écoute sur `http://localhost:8000` (Swagger : `/docs`). Les tables sont créées automatiquement au démarrage.

> Sans clés, mettez `AI_MODEL=test` dans `.env` : un faux modèle répond avec une revue de démonstration, sans réseau ni coût.

### 2. Frontend

```bash
cd frontend
npm ci
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm run dev
```

L'application est sur `http://localhost:3000`. Utilisez « Créer un compte » sur l'écran de connexion.

## Variables d'environnement

### Backend (`backend/.env`)

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `DATABASE_URL` | URL SQLAlchemy de la base | `sqlite:///./newsfoundry.db` |
| `JWT_SECRET_KEY` | Secret de signature des JWT. **Obligatoire** : sans lui, login et routes protégées répondent `503` | aucun |
| `JWT_ACCESS_TOKEN_MINUTES` | Durée de vie du jeton | `480` |
| `FRONTEND_ORIGINS` | Origines CORS autorisées, séparées par des virgules | `http://localhost:3000` |
| `PORT` | Port d'écoute de l'API | `8000` |
| `AI_MODEL` | `test` = faux modèle ; toute autre valeur = vrai modèle | `test` |
| `MAMMOUTH_KEY` | Clé API IA (si `AI_MODEL` ≠ `test`) | vide |
| `API_KEY_WORLD` | Clé World News API | vide |
| `APP_TIMEZONE` | Fuseau horaire de la « date du jour » donnée au modèle | `Europe/Paris` |

### Frontend (`frontend/.env.local`)

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `BACKEND_URL` | URL de l'API backend | `http://localhost:8000` |

## Tests et vérifications

Aucun test ne nécessite PostgreSQL, de clé API ni de réseau (SQLite en mémoire, faux modèle, appels réseau bloqués).

```bash
# Backend (depuis backend/)
uv run pytest -q                       # 24 tests
uv run pytest tests/test_call_modele.py -q   # seulement la logique IA
uv run ruff check src tests            # lint

# Frontend (depuis frontend/)
npm run lint
npx tsc --noEmit
npm run build                          # garder --webpack, déjà dans le script
```

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute ces mêmes étapes à chaque push et pull request.

## Fonctionnement en bref

1. Le navigateur appelle des **Server Actions** Next.js ; c'est le serveur Next qui contacte l'API en ajoutant `Authorization: Bearer <token>` lu dans un cookie `httpOnly`.
2. Un message utilisateur est enregistré, puis l'historique de la discussion et les sources déjà connues sont envoyés à l'agent IA.
3. L'agent répond soit avec du texte (`assistant`), soit avec une revue (`reviews`), soit en demandant des actualités (`top-news` / `search-news`). Dans ce dernier cas, le backend appelle World News API, sauvegarde les articles et redonne la main à l'agent (3 tours maximum).
4. La réponse finale est enregistrée comme message de la discussion.
5. Cliquer sur « Générer une revue de presse » dans une discussion crée la dernière revue de presse que le modèle a produite dans cette discussion.

Le détail (IA, base de données, reprise des conversations) est dans [`backend/README.md`](backend/README.md).

## Conseils d'utilisation

- Pour de meilleures performances et une réduction des coûts, il est conseillé de créer une conversation par revue de presse.
- Ne jamais mélanger des demandes différentes : le modèle pourrait produire des sorties erronées et le coût d'un appel pourrait fortement augmenter.
- Pensez à cliquer sur « Générer une revue de presse » pour qu'elle soit enregistrée dans la base de données et visible dans vos revues de presse.

## Deploiement

En production, l'application est répartie sur deux plateformes :

```text
Vercel                        Railway
┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────┐
│ Frontend Next.js     │ ───► │ Backend FastAPI      │ ───► │ PostgreSQL       │
│ (Server Actions)     │ HTTPS│ (conteneur Docker)   │      │ (service Railway)│
└──────────────────────┘      └──────────────────────┘      └──────────────────┘
```

Le front n'appelle jamais la base directement : il passe par le backend, qui est seul à connaître `DATABASE_URL`. Comme les appels API partent du serveur Next (Server Actions), il n'y a pas de CORS à gérer depuis le navigateur.


- DB + Backend via Railway : [**`https://newsfoundry-production-74e5dc89.up.railway.app`**](https://newsfoundry-production-74e5dc89.up.railway.app)
- EndPoint : [**`https://newsfoundry-production-74e5dc89.up.railway.app/docs`**](https://newsfoundry-production-74e5dc89.up.railway.app/docs)
- Frontend via Vercel : [**`news-foundry-seven.vercel.app`**](news-foundry-seven.vercel.app)

### 1. Base de données et backend sur Railway

1. Créer un projet Railway, puis **New → Database → PostgreSQL**. Railway expose la variable `DATABASE_URL` du service Postgres (format `postgresql://...`) ; elle est normalisée automatiquement en `postgresql+psycopg2://` par `backend/src/database.py`, inutile de la réécrire.
2. **New → GitHub Repo**, sélectionner ce dépôt. Le fichier [`railway.json`](railway.json) impose le builder `DOCKERFILE` avec `backend/Dockerfile`. Ce Dockerfile attend **la racine du dépôt** comme contexte (ses `COPY` commencent par `backend/`) : ne pas changer le *Root Directory* du service.
3. Dans l'onglet **Variables** du service backend, définir :

   | Variable | Valeur en production |
   | --- | --- |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (référence au service Postgres) |
   | `JWT_SECRET_KEY` | secret aléatoire long, par ex. `openssl rand -hex 32` — **jamais** celui du `.env` local |
   | `JWT_ACCESS_TOKEN_MINUTES` | `480` (ou moins) |
   | `FRONTEND_ORIGINS` | URL de production du front Vercel, ex. `https://newsfoundry.vercel.app` |
   | `AI_MODEL` | modèle réel (toute valeur autre que `test`) |
   | `MAMMOUTH_KEY` | clé Mammouth AI |
   | `API_KEY_WORLD` | clé World News API |
   | `APP_TIMEZONE` | `Europe/Paris` |
   | `MLFLOW_ENABLED` | `false` (tracing désactivé en production) |

   `PORT` est fourni par Railway et lu par `src/main.py` ; ne pas le fixer à la main.
4. **Settings → Networking → Generate Domain** pour obtenir une URL publique HTTPS.
5. Vérifier le déploiement : `curl https://<backend>.up.railway.app/health` doit renvoyer `{"status":"ok"}`, et `/docs` doit afficher Swagger. Les tables sont créées automatiquement au démarrage (lifespan → `init_db()`).
6. Optionnel : indiquer `/health` comme *Healthcheck Path* dans les réglages du service.

Pour reproduire l'image en local depuis **la racine du dépôt** :

```bash
docker build -f backend/Dockerfile -t newsfoundry-api .
```

### 2. Frontend sur Vercel

1. **Add New → Project**, importer ce dépôt.
2. **Root Directory** : `frontend/` (Framework détecté : Next.js). Le build par défaut (`npm run build`, avec `--webpack` dans le script) est conservé. Le `vercel.json` de la racine décrit un déploiement à deux services : en déployant uniquement le front, définir le *Root Directory* sur `frontend/` pour l'ignorer.
3. **Environment Variables** : `BACKEND_URL=https://<backend>.up.railway.app` — origine complète, **sans slash final**, pour Production, Preview et Development.
4. Déployer, puis récupérer le domaine de production (`https://<projet>.vercel.app`).
5. Revenir sur Railway et mettre ce domaine dans `FRONTEND_ORIGINS` (plusieurs origines possibles, séparées par des virgules, par ex. l'URL de production et une URL de preview stable), puis redéployer le backend.

Le cookie de session est `httpOnly` et `secure` en production : l'accès doit donc se faire en **HTTPS** des deux côtés.

### 3. Ordre de mise en ligne et vérifications

1. Railway : Postgres → backend → domaine public → `/health` OK.
2. Vercel : front avec `BACKEND_URL` → domaine de production.
3. Railway : `FRONTEND_ORIGINS` = domaine Vercel → redéploiement.
4. Test de bout en bout : création de compte, envoi d'un message, génération puis relecture d'une revue de presse dans `/reviews`.

### 4. Points de vigilance

- **Pas de migrations** : `init_db()` ne fait qu'un `create_all`, il ne modifie pas les tables existantes. Toute évolution des modèles demande une intervention manuelle sur la base Railway (ou l'ajout d'Alembic).
- **Pas de SQLite en production** : sans `DATABASE_URL`, le backend retombe sur un fichier SQLite local, perdu à chaque redéploiement du conteneur.
- **Secret JWT** : unique, aléatoire, stocké uniquement dans les variables Railway. Le changer invalide toutes les sessions en cours.
- **URLs** : documenter ici les domaines une fois publiés, par ex. `https://<projet>.vercel.app` (front) et `https://<backend>.up.railway.app` (API).

## Qualité de l'IA

Voir [`docs/ai-quality.md`](docs/ai-quality.md) : protocole d'évaluation, métriques (exactitude factuelle, fraîcheur, latence, coût). Les seuils sont des objectifs à valider sur un corpus éditorial, pas des résultats mesurés.

Voir aussi [`docs/analyse-performance.md`](docs/analyse-performance.md) : regard critique sur la qualité des résultats et la fluidité, avec mesures et pistes d'amélioration chiffrées.

## Prompt

Le prompt système est optimisé pour l'utilisation de l'application, voir [`backend/src/lib/prompt_systeme.py`](backend/src/lib/prompt_systeme.py).
Il définit le comportement, le ton et le format de réponse.

Pour que le modèle puisse demander des informations à `World News API`, son type de sortie est strictement défini. Ce type de sortie autorise 4 cas, gérés dans la fonction [`backend/src/lib/callModele.py`](backend/src/lib/callModele.py). Ils sont communiqués au modèle via le prompt système et via le paramètre `output_type` de l'agent PydanticAI :

- **`assistant`** : la réponse est renvoyée directement au front.
- **`reviews`** ou **`top-news`** : un appel à World News API est effectué, puis le modèle est rappelé avec les nouvelles données.
- **`review`** : la réponse est enregistrée en base de données comme revue de presse, puis renvoyée au front, qui sait qu'il s'agit d'une revue de presse et adapte l'affichage.
- **Tout autre type de sortie** : une erreur est levée et un message d'erreur est envoyé au front, qui l'affiche.

## Choix

### Pourquoi un pseudo RAG

La mise en place d'un véritable RAG a été envisagée ; néanmoins, quand on comprend la nature de l'application, il est évident qu'il n'est pas très adapté.
L'application crée des revues de presse **d'actualité**, et l'actualité ne convient pas au RAG : il pourrait trouver des ressources certes cohérentes avec la
demande de l'utilisateur, mais pas d'actualité, et renvoyer des éléments vieux de plusieurs années.
Si l'application évolue avec une fonctionnalité de recherche de documentation, le RAG pourrait alors s'avérer intéressant.

### Pourquoi pas de streaming

Le streaming évite à l'utilisateur d'attendre, mais rappelons que cette application a pour but de créer des revues de presse : elle doit trouver des sources et les résumer. Dans l'architecture, l'application cherche des informations via une autre API ; cette recherche ne peut pas être streamée car elle n'est jamais affichée. Pour les revues de presse, la réponse doit être reçue entièrement pour être traitée, puis validée avant d'être affichée. Le streaming ne devient intéressant que lorsque le modèle répond directement à l'utilisateur avec du texte.

