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
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
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
| `NEXT_PUBLIC_API_URL` | URL de l'API backend | `http://localhost:8000` |

## Tests et vérifications

Aucun test ne nécessite PostgreSQL, de clé API ni de réseau (SQLite en mémoire, faux modèle, appels réseau bloqués).

```bash
# Backend (depuis backend/)
uv run pytest -q                       # 22 tests
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

## Déploiement

- **Frontend** : Vercel, avec `NEXT_PUBLIC_API_URL` pointant vers l'origine HTTPS de l'API.
- **Backend** : Railway (ou tout hébergeur Docker). `backend/Dockerfile` doit être construit avec **la racine du dépôt** comme contexte (ses `COPY` commencent par `backend/`) :

  ```bash
  docker build -f backend/Dockerfile -t newsfoundry-api .
  ```

  Définir `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_MINUTES`, `FRONTEND_ORIGINS`, `AI_MODEL`, `MAMMOUTH_KEY` et `API_KEY_WORLD`.
- Utiliser un secret JWT unique et aléatoire, activer HTTPS, ne pas utiliser SQLite en production.

Aucune URL de déploiement n'est disponible à ce stade ; l'ajouter ici après publication.

## Qualité de l'IA

Voir [`docs/ai-quality.md`](docs/ai-quality.md) : protocole d'évaluation, métriques (exactitude factuelle, fraîcheur, latence, coût). Les seuils sont des objectifs à valider sur un corpus éditorial, pas des résultats mesurés.

Voir aussi [`docs/analyse-performance.md`](docs/analyse-performance.md) : regard critique sur la qualité des résultats et la fluidité, avec mesures et pistes d'amélioration chiffrées.

## Prompt

Le prompt système est optimisé pour l'utilisation de l'application, voir [`backend/src/lib/prompt_systeme.py`](backend/src/lib/prompt_systeme.py).
Il définit le comportement, le ton et le format de réponse.

## Choix

### Pourquoi un pseudo RAG

La mise en place d'un véritable RAG a été envisagée ; néanmoins, quand on comprend la nature de l'application, il est évident qu'il n'est pas très adapté.
L'application crée des revues de presse **d'actualité**, et l'actualité ne convient pas au RAG : il pourrait trouver des ressources certes cohérentes avec la
demande de l'utilisateur, mais pas d'actualité, et renvoyer des éléments vieux de plusieurs années.
Si l'application évolue avec une fonctionnalité de recherche de documentation, le RAG pourrait alors s'avérer intéressant.

### Pourquoi pas de streaming

Le streaming évite à l'utilisateur d'attendre, mais rappelons que cette application a pour but de créer des revues de presse : elle doit trouver des sources et les résumer. Dans l'architecture, l'application cherche des informations via une autre API ; cette recherche ne peut pas être streamée car elle n'est jamais affichée. Pour les revues de presse, la réponse doit être reçue entièrement pour être traitée, puis validée avant d'être affichée. Le streaming ne devient intéressant que lorsque le modèle répond directement à l'utilisateur avec du texte.

