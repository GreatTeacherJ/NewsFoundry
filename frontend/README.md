# NewsFoundry : Frontend

Interface web de NewsFoundry : Next.js 16 (App Router), React 19, TypeScript strict, CSS Modules.

## Lancement

```bash
npm ci
echo "BACKEND_URL=http://localhost:8000" > .env.local 
npm run dev                                                      # http://localhost:3000
```

Le backend doit tourner (voir [`../backend/README.md`](../backend/README.md)).

## Commandes

| Commande | Rôle |
| --- | --- |
| `npm run dev` | Serveur de développement |
| `npm run lint` | ESLint |
| `npx tsc --noEmit` | Vérification TypeScript |
| `npm run build` | Build de production (le script contient `--webpack`, à conserver) |
| `npm start` | Sert le build de production |

Ordre de vérification utilisé en CI : `npm ci` → `npm run lint` → `npx tsc --noEmit` → `npm run build` (avec `BACKEND_URL=http://localhost:8000`). Il n'y a pas de tests automatisés côté frontend.

Prérequis : Node 22.

## Pages

| Route | Fichier | Contenu |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | Connexion / création de compte (`LoginForm`) |
| `/home` | `src/app/home/page.tsx` | Nouvelle discussion (écran d'accueil du chat) |
| `/chat/[id]` | `src/app/chat/[id]/page.tsx` | Discussion existante |
| `/reviews` | `src/app/reviews/page.tsx` | Bibliothèque des revues de presse |

## Structure

```text
src/
├── app/                 # Pages (App Router) et styles globaux
├── components/          # Composants + CSS Modules associés
│   ├── AppShell         # Mise en page : barre latérale (liste des discussions), déconnexion
│   ├── Header           # Navigation Chat / Revues
│   ├── LoginForm        # Connexion et inscription
│   ├── ChatView         # Messages, saisie, envoi, création de discussion
│   ├── GenerateReviewModal  # Fenêtre « Générer une revue de presse »
│   ├── ReviewsView / ReviewModal  # Liste et lecture des revues
├── lib/
│   ├── api.ts           # Client API (Server Action) + types Discussion/Message/PressReview
│   ├── exportApi.ts     # ApiError et jsonBody() (hors "use server")
│   └── loginActions.ts  # loginAction / logoutAction (cookie)
├── proxy.ts             # Protection des routes (redirections selon le cookie)
└── types/typeApi.ts     # Types supplémentaires
```

`@/*` correspond à `src/*`.

## Authentification et appels API

- **Cookie** : `loginAction` appelle `/auth/login` côté serveur et stocke le JWT dans le cookie `token` (`httpOnly`, `sameSite=lax`, `secure` en production, durée 8 h). Le JavaScript du navigateur ne peut pas le lire.
- **`api<T>(path, options)`** (`lib/api.ts`) est marqué `"use server"` : il s'exécute sur le serveur Next, lit le cookie, ajoute `Authorization: Bearer <token>` (sauf pour `/auth/register` et `/auth/login`) et appelle l'API avec `cache: "no-store"`. Les composants client l'appellent comme une fonction normale. Il n'y a donc pas de CORS à gérer côté navigateur.
- **Erreurs** : une réponse non `2xx` devient une `ApiError(message, status)` portant le champ `detail` renvoyé par le backend ; un serveur injoignable donne un message dédié. Les composants affichent ce message.
- **`proxy.ts`** (middleware Next 16) : sans cookie, toute page autre que `/` redirige vers `/` ; avec cookie, `/` redirige vers `/home`. Il ne vérifie que la **présence** du cookie, pas la validité du jeton : un jeton expiré fait échouer les appels API, qui renvoient `401`.
- **Déconnexion** : `logoutAction` supprime le cookie.

## Fonctionnement du chat

1. Sur `/home`, au premier message, `ChatView` crée une discussion (`POST /discussions`, titre = début du message, 80 caractères) puis envoie le message et redirige vers `/chat/{id}`.
2. `POST /discussions/{id}/messages` renvoie `[message_utilisateur, réponse_ia]` ; les deux sont ajoutés à la liste affichée. Pendant l'attente (la réponse IA peut prendre plusieurs secondes) un indicateur de chargement s'affiche et l'envoi est bloqué.
3. En ouvrant `/chat/{id}`, l'historique est rechargé via `GET /discussions/{id}/messages` : une conversation reprend donc là où elle s'est arrêtée, y compris après rechargement de la page.
4. Les messages sont rendus en **Markdown** (`react-markdown` + `remark-gfm`). Les trois rôles (`user`, `assistant`, `reviews`) ont des styles distincts.
5. Le bouton « Générer une revue de presse » (visible dans une discussion existante) vérifie qu'un message `reviews` existe, appelle `POST /discussions/{id}/press-reviews`, puis redirige vers `/reviews`. Sinon il invite à demander une revue à l'assistant.
6. La barre latérale (`AppShell`) recharge la liste des discussions à chaque changement de page.

Le champ « Thème » de la fenêtre de génération de revue n'est pas encore relié : le titre de la revue est construit par le backend (« Revue de presse — {titre de la discussion} »).

## Déploiement

Déployer ce dossier sur Vercel et définir `BACKEND_URL` sur l'URL HTTPS de l'API. Côté backend, ajouter l'origine du site dans `FRONTEND_ORIGINS`.
