# NewsFoundry

Assistant de veille et de synthèse d’actualité destiné aux médias et aux journalistes. L’interface comprend la connexion, un espace de discussion, l’historique personnel et la bibliothèque des revues de presse.

## État des fonctionnalités

- Inscription et connexion par email/mot de passe avec jeton JWT.
- Discussions, messages et revues de presse enregistrés dans PostgreSQL.
- Les ressources sont privées et filtrées selon l’utilisateur authentifié.
- L’interface affiche les erreurs renvoyées par l’API.
- Les réponses assistant et revues sont actuellement des réponses de démonstration. Le LLM, PydanticAI et WorldNewsAPI restent à intégrer.

## Prérequis

- Docker
- Python 3.13 et `uv`
- Node.js 22.19 ou une version compatible avec Next.js
- npm

## Installation et démarrage local

1. Depuis `backend/`, copier `.env.example` vers `.env`, remplacer `JWT_SECRET_KEY` par un secret aléatoire fort, puis installer les dépendances :

   ```bash
   cd backend
   cp .env.example .env
   uv sync
   ```

2. Démarrer PostgreSQL depuis `backend/` :

   ```bash
   docker run --name newsfoundry_db \
     -e POSTGRES_USER=user \
     -e POSTGRES_PASSWORD=password \
     -e POSTGRES_DB=newsfoundry \
     -p 5432:5432 \
     -d postgres:17
   ```

3. Démarrer l’API depuis `backend/` :

   ```bash
   uv run --env-file .env src/main.py
   ```

   L’API écoute sur `http://localhost:8000`. Sa documentation interactive est disponible dans `/docs`.

4. Dans un autre terminal, configurer et démarrer le frontend :

   ```bash
   cd frontend
   npm install
   ```

   Créer `frontend/.env.local` avec `NEXT_PUBLIC_API_URL=http://localhost:8000`, puis démarrer :

   ```bash
   npm run dev
   ```

   L’application est disponible sur `http://localhost:3000`. Créer un compte via le lien « Créer un compte » sur l’écran de connexion.

## API

| Méthode | Route | Fonction |
| --- | --- | --- |
| `POST` | `/auth/register` | Créer un compte |
| `POST` | `/auth/login` | Obtenir un JWT |
| `GET` | `/auth/me` | Consulter le compte courant |
| `GET`, `POST` | `/discussions` | Lister ou créer ses discussions |
| `GET`, `PATCH`, `DELETE` | `/discussions/{id}` | Lire, modifier ou supprimer une discussion propriétaire |
| `GET`, `POST` | `/discussions/{id}/messages` | Lire ou envoyer un message |
| `POST` | `/discussions/{id}/press-reviews` | Créer une revue depuis la discussion |
| `GET` | `/press-reviews` | Lister ses revues |
| `GET`, `PATCH`, `DELETE` | `/press-reviews/{id}` | Lire, modifier ou supprimer une revue propriétaire |

Les requêtes authentifiées utilisent `Authorization: Bearer <token>`. Une ressource inaccessible ou appartenant à un autre compte renvoie `404`.

## Vérifications

Depuis `backend/` :

```bash
uv run pytest -q
uv run ruff check src tests
```

Depuis `frontend/` :

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## CI

Les workflows GitHub Actions exécutent la suite pytest/Ruff du backend et ESLint/TypeScript/build du frontend à chaque push ou pull request.

## Améliorations IA

Voir [`docs/ai-quality.md`](docs/ai-quality.md) pour le protocole d’évaluation, les métriques de qualité factuelle, de fraîcheur, de latence, de coût et les objectifs initiaux. Les seuils indiqués restent à valider sur un corpus éditorial.

## Déploiement

- Frontend : déployer `frontend/` sur Vercel et définir `NEXT_PUBLIC_API_URL` sur l’origine HTTPS de l’API.
- Backend : déployer `backend/` sur Railway. Définir `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_MINUTES` et `FRONTEND_ORIGINS` comme variables d’environnement Railway.
- Utiliser un secret JWT unique et aléatoire, activer HTTPS, et ne pas utiliser une base SQLite en production.

Aucune URL de déploiement n’est disponible à ce stade ; l’ajouter ici après publication des services.
