# Regard critique sur la performance de NewsFoundry

Analyse réalisée le 16 novembre 2026 sur le code du dépôt (backend FastAPI + PydanticAI, frontend Next.js 16). Elle porte sur deux axes : la **qualité des résultats** rendus à l'utilisateur et la **fluidité des interactions**. Chaque piste s'appuie sur une mesure, une trace réelle ou une ligne de code citée, puis détaille comment la réaliser.

## 1. Ce qui a été mesuré, et ce qui ne l'a pas été

Il faut le dire d'emblée : **l'application n'a aucune instrumentation** (aucun chronomètre, aucun compteur de tokens, aucun log de latence dans `backend/src`). Les chiffres ci-dessous viennent donc de bancs d'essai jetables lancés pour cette analyse, pas de la production.

| Source | Contenu | Fiabilité |
| --- | --- | --- |
| Bancs d'essai backend | Taille des prompts, nombre de requêtes SQL, comportement du pool de connexions, avec un faux agent et un faux appel World News (aucun appel payant) | Mesuré, reproductible |
| Banc d'essai frontend | `npm run build`, taille des chunks JS, coût de rendu de la liste Markdown (Node, `renderToStaticMarkup`) | Mesuré, indicatif (≠ navigateur) |
| `backend/conversation.txt` | Seule trace réelle avec le vrai modèle : 1 question, 3 appels à l'agent, 2 articles. Fichier du 9 nov., **antérieur** aux changements du 11 nov. (pseudo RAG, prompt « n'appelle plus l'API ») | Réel mais ancien et unique |
| Lecture du code et documentation Next.js | Comportements déduits (marqués « déduit ») | À valider par mesure |

**Non mesuré** : la latence réelle de bout en bout avec Mammouth et World News API, le coût en euros, les performances de PostgreSQL (le conteneur `newsfoundry_db` existe mais n'est pas démarré ; les mesures SQL sont sur SQLite en mémoire), et la fluidité réelle dans un navigateur. Les tokens sont estimés à 3,5 caractères par token pour du français ; l'ordre de grandeur est fiable, pas la valeur exacte.

La seule mesure de latence réelle disponible : un tour de conversation **sans** recherche d'actualités a pris **0,27 s** (écart entre les horodatages du message utilisateur et de la réponse en base, discussion 17). Aucun tour avec recherche n'a été chronométré.

## 2. Synthèse

| # | Piste | Axe | Effort | Priorité |
| --- | --- | --- | --- | --- |
| 1 | Instrumenter et construire un jeu d'évaluation | Qualité + fluidité | S | Première |
| 2 | Empêcher par construction les rappels d'API redondants | Qualité + latence | S | Haute |
| 3 | Conserver titre, média et date des sources | Qualité | S–M | Haute |
| 4 | Plafonner et compacter les sources réinjectées | Qualité + coût + latence | M | Haute |
| 5 | Libérer la connexion DB et borner les délais pendant l'appel IA | Fluidité + robustesse | M | Haute |
| 6 | Retour progressif à l'écran (statuts, puis streaming) | Fluidité | M–L | Haute |
| 7 | Rendre la saisie fluide (mémoïsation des messages) | Fluidité | S | Moyenne |
| 8 | Corriger la navigation et les rechargements inutiles | Fluidité | M | Moyenne |
| 9 | Petits défauts à fort impact (brouillon perdu, titres, jeton expiré) | Fluidité + qualité perçue | S | Moyenne |
| 10 | Valider la sortie de la revue | Qualité | M | Après la piste 1 |
| 11 | Réduire les requêtes SQL à l'enregistrement des articles | Fluidité | S | Faible |

---

## 3. Qualité des résultats

### Piste 1 — Instrumenter et construire un jeu d'évaluation

**Constat.** `grep` sur `backend/src` ne trouve ni `usage`, ni `perf_counter`, ni journal de latence. `docs/ai-quality.md` fixe des objectifs (95 % d'affirmations sourcées, p95 < 8 s) mais précise qu'ils « ne sont pas des résultats mesurés ». La CI utilise uniquement `TestModel`, qui renvoie toujours la même revue : elle prouve que le code fonctionne, pas que les réponses sont bonnes. Sans mesure, aucune des pistes suivantes ne peut être validée.

**Réalisation.**
1. Dans `call_modele_chat`, chronométrer chaque étape (appel LLM, appel World News, sauvegarde) et lire `run.usage()` (disponible dans PydanticAI 2.27.1) pour obtenir les tokens d'entrée et de sortie. Journaliser une ligne structurée par message : `discussion_id`, nombre de tours, tokens, durées, type de sortie.
2. Constituer un jeu d'une vingtaine de scénarios dans `backend/tests/eval/` : question, articles figés (fixtures JSON), critères de réussite vérifiables par code (format de la revue, présence de la section Sources, langue de la réponse, refus hors périmètre, demande de clarification si le pays manque).
3. Le lancer à la demande avec le vrai modèle (`AI_MODEL=mammouth`), jamais en CI, et conserver les résultats par version de prompt.

**Effort** : S. **Vérification** : un tableau p50/p95 de latence et de tokens, et un taux de réussite par critère, reproductibles à chaque modification du prompt.

### Piste 2 — Empêcher par construction les rappels d'API redondants

**Constat (trace réelle, `conversation.txt`).** Pour une seule question (« les actualités d'aujourd'hui »), l'agent a été appelé **3 fois**, et les 3 sorties étaient des `NeedTopNews` quasi identiques (`date=None`, puis `date=2026-11-09`, puis `max_news_per_cluster=3`). Les mêmes articles ont été téléchargés 3 fois (6 992 caractères à chaque fois) et le contexte envoyé au modèle est passé de 7 006 à 14 000 caractères entre le 2e et le 3e appel. La trace s'arrête après le 3e appel, sans réponse finale, ce qui correspond à la limite `MAX_NEWS_ROUNDS = 3` (déduit : la trace ne contient pas le message d'erreur lui-même) : l'utilisateur n'a vraisemblablement rien reçu. Depuis, le prompt de relance dit « N'appelle plus l'API », mais c'est une consigne, pas une garantie.

**Pourquoi c'est un problème.** Chaque tour inutile coûte un appel LLM complet (et le prompt système de ≈ 2 350 tokens) plus un appel réseau de jusqu'à 50 s, pour un résultat nul.

**Réalisation.** `Agent.run_sync` accepte un paramètre `output_type` (vérifié sur la version installée). Après le premier appel à World News, relancer l'agent avec `output_type=ResModel` uniquement : le modèle ne peut plus redemander des news, il doit conclure. Les tours deviennent bornés à 2 par message, la constante `MAX_NEWS_ROUNDS` et l'erreur « trop de demandes » disparaissent. En complément, mémoriser dans la discussion les couples (`kind`, paramètres) déjà exécutés pour ne pas refaire un appel identique d'un message à l'autre.

**Effort** : S (quelques lignes + adaptation de 2 tests). **Gain attendu** : maximum 2 appels LLM par message au lieu de 3 dans le pire cas, plus aucun échec sur ce motif. **Vérification** : la piste 1 doit montrer « nombre de tours = 1 ou 2 » pour 100 % des messages.

### Piste 3 — Conserver titre, média et date des sources

**Constat (mesuré).** `save_article` ne stocke que `url` et `article.text` ; `_source_text` ne renvoie que `source.content`. Test réalisé avec un article complet (titre, auteur, date, catégorie) : ce que le modèle relit au tour suivant est `"Corps de l'article."` — plus de titre, de date, d'auteur ni de média. Or le prompt exige que la revue se termine par « **Sources** : [Média et date de publication de chaque article utilisé] ». Dès la 2e question d'une discussion (« fais-en une revue »), le modèle ne dispose plus de ces informations et doit soit les omettre, soit les inventer, ce qui contredit la règle « n'invente jamais ».

**Réalisation.**
1. Ajouter à `Source` les colonnes `title`, `publish_date`, `author`, `category` (tous nullables). Le nom du média se déduit du domaine de l'URL (ex. `www.lefigaro.fr` → « Le Figaro » via un petit dictionnaire, sinon le domaine).
2. `save_article` renseigne ces champs ; les sources déjà en base sont mises à jour si l'URL existe (aujourd'hui leur contenu n'est jamais rafraîchi).
3. `_source_text` produit un bloc lisible : `### Titre — lefigaro.fr — 2026-11-09 08:06\nURL\nTexte`.
4. Prérequis : le projet n'a pas de migrations (voir `backend/README.md`). Introduire Alembic avant, sinon `ALTER TABLE` manuel. Profiter de l'occasion pour rendre `Source.url` unique (il n'est aujourd'hui qu'indexé, donc deux requêtes simultanées peuvent créer des doublons).

**Effort** : S–M. **Vérification** : un test qui sauvegarde un article puis contrôle que le prompt du tour suivant contient titre, domaine et date ; dans le jeu d'évaluation, 100 % des revues citent un média et une date présents dans les sources.

### Piste 4 — Plafonner et compacter les sources réinjectées

**Constat (mesuré).** À chaque message, **toutes** les sources de la discussion sont recollées dans le prompt. Avec des articles de taille réelle (≈ 2 200 caractères, comme dans la trace) :

| Articles récupérés | Prompt du tour suivant | ≈ tokens |
| --- | --- | --- |
| 5 | 12 615 car. | 3 600 |
| 20 | 49 995 car. | 14 300 |
| 50 | 124 785 car. | 35 700 |

Sur une discussion de 6 questions, chacune ramenant 5 nouveaux articles, le premier prompt de chaque tour passe de ≈ 3 tokens à ≈ 15 700, soit **≈ 61 000 tokens d'entrée cumulés** (prompt système inclus, et seulement pour le premier appel de chaque tour : c'est une borne basse). Un « merci » ou une question de méthode paie le même prix qu'une demande de synthèse. Dans la trace réelle, 27 % du JSON envoyé est constitué de métadonnées inutiles au modèle (image, vidéo, identifiants).

**Pourquoi c'est un problème.** Le temps de réponse d'un LLM augmente avec la taille de l'entrée ; le coût aussi ; et sur une longue discussion on s'expose à dépasser la fenêtre de contexte, ce qui se traduirait par une erreur 502 sur des conversations anciennes précisément.

**Réalisation.**
1. **Compacter** : ne sérialiser que `title`, `text`, `url`, `publish_date`, `author`, `category` (gain mesuré sur la trace : −13 %), et tronquer `text` à ≈ 1 200 caractères (gain mesuré : **−46 %** au total sur la trace).
2. **Plafonner** : définir un budget de tokens pour les sources (ex. 6 000), en gardant d'abord les plus récemment liées à la discussion. Sur le scénario à 6 questions, un plafond de 6 000 tokens ramène le cumul d'entrée de ≈ 61 400 à ≈ 41 300 (**−33 %**) et empêche toute croissance sans limite.
3. **Cibler** : ne réinjecter que les sources pertinentes pour la question (classement simple par recouvrement de mots-clés avec le message et la date), puis, si ça ne suffit pas, passer à des embeddings.
4. Option : générer un court résumé à l'enregistrement de chaque article avec un modèle léger et réinjecter le résumé plutôt que le texte intégral (demande une colonne `summary`).

**Effort** : M. **Vérification** : tokens d'entrée par message (piste 1) plafonnés quel que soit le nombre d'articles ; le jeu d'évaluation ne doit pas perdre en qualité de revue.

### Piste 10 — Valider la sortie de la revue

**Constat.** Le format de la revue (titre `**REVUE DE PRESSE [THÈME] - [date]**`, puces, ligne `**Sources**`) n'est imposé que par le prompt. Le frontend copie ensuite le texte tel quel dans la bibliothèque (`create_press_review` recopie `content`). Aucune défaillance n'a été mesurée à ce jour, faute d'instrumentation : cette piste est **préventive** et dépend de la piste 1.

**Réalisation.** PydanticAI propose `@agent.output_validator` et `ModelRetry`. Ajouter un validateur qui, pour `kind="reviews"`, vérifie l'en-tête, la présence de la ligne `Sources` et que les médias cités apparaissent dans les sources de la discussion ; en cas d'écart, `raise ModelRetry("…")` (1 relance maximum pour borner le coût). Les revues rejetées sont comptées dans les journaux de la piste 1.

**Effort** : M. **Vérification** : taux de relance et taux de revues conformes dans le jeu d'évaluation. À activer seulement si ce taux révèle un vrai problème, car chaque relance ajoute un appel LLM.

---

## 4. Fluidité des interactions

### Piste 5 — Libérer la connexion DB et borner les délais pendant l'appel IA

**Constat (mesuré).** `create_message` garde la session SQLAlchemy ouverte pendant tout l'appel au modèle, donc une connexion du pool est occupée pendant toute la génération. Le pool utilise les valeurs par défaut (5 connexions + 10 de dépassement, attente maximale 30 s). Simulation avec la configuration réelle : **20 messages simultanés, appel IA de 5 s** → 15 servis en 5,0 s, **5 servis en 10,0 s** (ils attendaient une connexion). Déduit : si l'IA prend 30 s ou plus, au-delà de 15 messages simultanés l'attente dépasse `pool_timeout` et la requête échoue en 500. Les endpoints sont des fonctions synchrones : FastAPI les exécute dans un pool de **40 threads** (mesuré), chacun bloqué pendant l'appel IA.

Les délais ne sont pas bornés de façon réaliste : le client OpenAI de PydanticAI a un délai de lecture de **600 s** et **2 relances automatiques** (mesuré sur le fournisseur configuré) ; l'appel World News est limité à 50 s par tour. Un utilisateur peut donc voir le chargement tourner plusieurs minutes.

**Réalisation.**
1. Découper `create_message` en trois phases : (a) session courte : vérifier le propriétaire, enregistrer le message utilisateur, **commit**, lire historique et sources sous forme de données simples ; (b) appel IA **sans session** ; (c) session courte : enregistrer les articles et la réponse. `call_modele_chat` reçoit alors l'historique et les sources en paramètres au lieu d'une session.
2. Borner les délais : `ModelSettings(timeout=60, max_tokens=…)`, `UsageLimits(request_limit=3)` (vérifiés présents), délai World News ramené à 15 s avec une seule relance.
3. Option à plus long terme : passer l'endpoint en `async def` avec `agent.run` et un client HTTP asynchrone pour ne plus bloquer de threads.
4. Conséquence à gérer : le message utilisateur est commité avant la réponse, donc en cas d'échec il faut le marquer ou le supprimer (le comportement « pas de message orphelin » ajouté récemment devra être refait explicitement).

**Effort** : M. **Vérification** : rejouer la simulation (20 messages simultanés) : tous servis en ≈ durée de l'IA, sans attente de connexion ; temps d'attente maximal documenté et testé.

### Piste 6 — Retour progressif à l'écran

**Constat.** La réponse n'arrive qu'à la fin : `run_sync`, puis un seul JSON `[message, réponse]`. Côté interface, l'utilisateur voit uniquement un indicateur de points (`busy`) sans savoir si l'assistant recherche des articles ou rédige. Un tour avec recherche enchaîne un appel LLM, un appel World News (jusqu'à 50 s), puis un second appel LLM ; chaque étape est invisible. Le gain est surtout perceptuel, car la latence totale reste la même. De plus, Next.js envoie les Server Actions **une par une** : tant qu'une réponse IA est en cours, les autres appels `api()` du même client (changer de discussion, recharger la liste) attendent (documentation Next.js, « Sequential dispatch on the client » ; déduit, non chronométré).

**Réalisation, en deux étapes.**
1. **Statuts d'étape (rapide à livrer).** Ajouter un endpoint `POST /discussions/{id}/messages/stream` renvoyant du Server-Sent Events via `StreamingResponse`, avec des événements `status` (« Recherche des actualités… », « Rédaction de la réponse… ») puis `message` (le résultat final). Le navigateur ne peut pas lire le cookie `httpOnly` contenant le jeton, donc il faut un **Route Handler Next.js** (`app/api/chat/stream/route.ts`) qui lit le cookie, ajoute l'en-tête `Authorization` et relaie le flux. Un Route Handler n'est pas soumis à l'envoi séquentiel des Server Actions.
2. **Streaming du texte.** Utiliser `agent.run_stream_events` (présent dans PydanticAI 2.27.1) pour diffuser le champ `content` de la sortie structurée au fil de l'eau. C'est plus délicat avec une sortie de type union (`ResModel | NeedTopNews | NeedSearchNews`) : prototyper d'abord pour confirmer que les sorties partielles sont exploitables, sinon se limiter à l'étape 1.
3. Côté `ChatView`, afficher le statut courant à la place des points, et ajouter le texte reçu dans une bulle provisoire.

**Effort** : M (étape 1), L (étape 2). **Vérification** : mesurer le « temps jusqu'au premier retour visible » (statut ou premier mot) avant/après avec la piste 1, objectif < 1 s ; vérifier qu'on peut naviguer pendant qu'une réponse est en cours.

### Piste 7 — Rendre la saisie fluide

**Constat (mesuré).** Dans `ChatView`, l'état `draft` (le texte tapé) et la liste `messages` sont dans le même composant, et chaque message passe par `ReactMarkdown`, qui reparse le texte à chaque rendu. Chaque frappe re-rend donc toute la liste. Coût mesuré du rendu de la liste avec une revue de presse de 765 caractères par message (médiane sur 20 rendus, Node) :

| Messages affichés | Médiane | p90 |
| --- | --- | --- |
| 10 | 9,7 ms | 11,2 ms |
| 30 | 20,8 ms | 27,8 ms |
| 60 | 39,2 ms | 48,1 ms |

Le budget d'une image à 60 Hz est de 16 ms : **dès ~15 messages de ce type, chaque frappe peut dépasser une image**. Réserve : mesure faite avec `renderToStaticMarkup` (rendu complet du texte), sans la réconciliation du DOM réel, donc à confirmer avec le Profiler de React DevTools. Une discussion longue contenant des revues est précisément le cas d'usage du produit.

**Réalisation.**
1. Extraire `MessageItem` (icône, `ReactMarkdown`, horodatage) dans un composant enveloppé par `React.memo` : les messages existants ne sont plus recalculés tant que leur contenu ne change pas.
2. Extraire le formulaire de saisie dans un composant `Composer` qui possède l'état `draft`, de sorte que taper ne touche plus à la liste.
3. Les `key` sont déjà stables (`message.id`), rien à changer.

**Effort** : S. **Vérification** : le Profiler doit montrer 0 rendu de `MessageItem` pendant la saisie ; coût par frappe nettement inférieur à 16 ms avec 60 messages.

### Piste 8 — Corriger la navigation et les rechargements inutiles

**Constat (code).**
- `AppShell` (barre latérale) est instancié **dans chaque page** (`home`, `chat/[id]`, `reviews`) et non dans un layout partagé. Il est donc remonté quand on passe d'une page à l'autre, et son `useEffect` (dépendances `[pathname, router]`, `AppShell.tsx:24`) relance `GET /discussions` à chaque changement de chemin, avec un nouvel état « Chargement… ».
- Après le premier message depuis `/home`, `ChatView` crée la discussion, affiche la réponse, puis fait `router.replace('/chat/{id}')`. Cette autre page remonte `ChatView` et rappelle `GET /discussions/{id}/messages` pour récupérer ce qu'on vient déjà de recevoir.
- La liste `GET /discussions` n'a ni pagination ni limite.
- Tous ces appels passent par une Server Action : le navigateur appelle Next.js, qui appelle FastAPI. C'est un saut de plus par lecture, et ces lectures sont aussi soumises à l'envoi séquentiel évoqué plus haut.

**Réalisation.**
1. Créer un groupe de routes `src/app/(app)/layout.tsx` qui contient `AppShell` une seule fois ; il survit aux changements de page et garde sa liste en mémoire.
2. Mettre à jour la liste de façon locale (ajout de la discussion créée, mise à jour de `updated_at`) au lieu de la recharger en entier.
3. Lire les données depuis des Server Components (la page récupère les messages côté serveur et les passe à `ChatView` en `initialMessages`), ce qui supprime le saut client → serveur et le rechargement après `router.replace`.
4. Ajouter `?limit=` et `?offset=` à `GET /discussions` et charger la suite au défilement.

**Effort** : M. **Vérification** : compter les appels réseau par parcours (connexion → premier message → ouverture de la revue) avant/après ; objectif : aucun rechargement de la liste ni des messages déjà connus.

### Piste 9 — Petits défauts à fort impact

Chacun se corrige en quelques lignes ; ensemble ils pèsent plus sur l'impression de fluidité que beaucoup d'optimisations.

| Constat (code) | Conséquence | Correctif |
| --- | --- | --- |
| `ChatView.tsx` : `const mes = draft; setDraft("")` avant l'envoi, et le `catch` ne le restaure pas. Le backend supprime en plus le message en cas d'échec IA (502) | Si l'assistant échoue, **l'utilisateur perd le texte qu'il a rédigé** ; il doit le retaper | Restaurer le brouillon dans le `catch` (`setDraft(mes)`) |
| `AppShell.tsx` affiche « Discussion du » + date pour toutes les discussions ; l'en-tête affiche toujours « Nouvelle discussion ». Le titre (début du premier message) est pourtant enregistré | Impossible de retrouver une conversation dans la liste : toutes se ressemblent | Afficher `discussion.title` dans la liste et dans l'en-tête |
| `.env.example` fixe `JWT_ACCESS_TOKEN_MINUTES=60` alors que le cookie vit 8 h (`loginActions.ts`) ; `proxy.ts` ne vérifie que la **présence** du cookie ; aucun traitement du `401` côté `api()` (aucune occurrence dans le frontend) | Au bout d'une heure avec cette configuration, l'utilisateur reste « connecté » mais chaque action échoue avec « Jeton invalide ou expiré » sans redirection | Dans `api()`, sur `401` : supprimer le cookie et rediriger vers `/` ; aligner la durée du jeton et du cookie |

**Effort** : S pour l'ensemble. **Vérification** : tests manuels des trois scénarios (échec simulé, liste de discussions, jeton expiré) ; ajouter un test d'`api()` pour le `401`.

### Piste 11 — Réduire les requêtes SQL à l'enregistrement des articles

**Constat (mesuré).** `save_article` fait une requête par article pour chercher l'URL, une insertion avec `flush`, puis une lecture et une insertion pour le lien : entre 3,6 et 4,4 requêtes par article (22 requêtes pour 5 articles, 77 pour 20, 182 pour 50, y compris la lecture de l'historique). Sur SQLite en mémoire cela représente 10 à 35 ms, négligeable devant le LLM. Sur PostgreSQL distant (non mesuré), à ≈ 1 ms par aller-retour, 50 articles ajouteraient ≈ 0,2 s. **Priorité faible**, à traiter avec la piste 3 puisque la fonction est réécrite à ce moment.

**Réalisation.** Une requête `WHERE url IN (...)` pour retrouver les sources connues, une insertion groupée des nouvelles, une insertion groupée des liens manquants ; avec la contrainte d'unicité sur `Source.url` de la piste 3.

---

## 5. Vérifié, mais sans piste prioritaire

- **Taille du JavaScript.** `npm run build` (15 s) : 22 fichiers JS pour **≈ 1 100 Ko** (≈ 342 Ko compressés en gzip). Le chunk de la bibliothèque Markdown (≈ 161 Ko) n'est chargé que sur `/home`, `/chat/[id]` et `/reviews`, pas sur la page de connexion (18 Ko propres à la page). C'est correct et ne justifie pas de travail à ce stade. Un chargement différé de `react-markdown` ne vaudrait que si la page de connexion devenait plus lourde.
- **Suppression d'une discussion.** Avec 100 messages, `delete_discussion` fait 5 requêtes SQL (suppressions groupées par SQLAlchemy) : pas de problème de N+1.
- **Tour simple sans recherche** : 0,27 s mesuré en conditions réelles. Les cas lents se situent donc dans les tours avec recherche d'actualités, ce que la piste 1 doit permettre de chiffrer.

## 6. Ordre de réalisation conseillé

1. **Piste 1** (instrumentation + jeu d'évaluation) : sans elle, les gains annoncés restent théoriques.
2. **Pistes 2 et 9** : modifications courtes, bénéfice immédiat (moins d'échecs, brouillon conservé, titres visibles).
3. **Pistes 3 et 4** : même zone de code (`callModele.py`, modèle `Source`) ; introduire Alembic avant, car la piste 3 modifie le schéma.
4. **Piste 5** puis **piste 6** : restructurer `create_message` d'abord, c'est un prérequis pour diffuser les statuts proprement.
5. **Pistes 7, 8 et 11** : travail frontend et SQL, indépendant du reste.
6. **Piste 10** : à décider selon ce que la piste 1 révèle.

## 7. Indicateurs de suivi proposés

Ces indicateurs reprennent le vocabulaire de `docs/ai-quality.md` et deviennent mesurables avec la piste 1.

| Indicateur | Point de départ | Cible proposée |
| --- | --- | --- |
| Tours LLM par message | Jusqu'à 3 (trace du 9 nov.) | ≤ 2 |
| Tokens d'entrée par message | Croît sans limite (≈ 15 700 à la 6e question dans le scénario testé) | Plafonné (ex. ≤ 9 000) |
| Premier retour visible pour l'utilisateur | = fin de la réponse (non chronométré) | < 1 s |
| Revues citant média et date issus des sources | Non mesuré | 100 % sur le jeu d'évaluation |
| Rendu de la liste à chaque frappe (60 messages) | 39 ms | < 16 ms |
| Messages simultanés sans échec (IA de 30 s) | ≈ 15 (déduit) | ≥ 40 |

Les cibles sont des propositions à confirmer avec les premières mesures réelles, pas des résultats.

## Annexe : méthode des mesures

Bancs d'essai écrits dans `/tmp/mammouth/` (non versionnés). Je peux les ajouter à `backend/scripts/` si vous voulez pouvoir les rejouer.

- **Prompts et SQL** : `call_modele_chat` exécuté avec un faux agent et un faux `fetch_world_news` ; des articles de 2 200 caractères pour correspondre à la trace réelle ; requêtes comptées via l'évènement SQLAlchemy `before_cursor_execute`.
- **Pool** : application FastAPI minimale avec `Depends(get_session)` identique au code, pool `QueuePool(5, 10, timeout=30)`, 20 threads, attente simulée de 5 s à la place du LLM.
- **Délais du client modèle** : lecture directe de `OpenAIProvider(...).client.timeout` et `.max_retries`.
- **Rendu Markdown** : `renderToStaticMarkup` de 10, 30 et 60 articles `ReactMarkdown` + `remark-gfm`, 5 rendus de chauffe puis 20 mesurés, médiane et p90.
- **Bundle** : `npm run build` (Next.js 16.4.3, webpack), somme des tailles de `.next/static/chunks`, chunks par page lus dans les manifestes `client-reference`.
