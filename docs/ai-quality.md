# Qualité et performance IA

La génération IA et la connexion WorldNewsAPI ne sont pas encore implémentées. Les mesures ci-dessous sont des objectifs initiaux à confirmer sur un jeu de test éditorial représentatif avant toute mise en production.

| Axe | Mesure de départ | Implémentation proposée | Objectif mesurable |
| --- | --- | --- | --- |
| Exactitude factuelle | Évaluer 100 questions d’actualité avec 3 journalistes et noter la part d’affirmations corroborées par une source | Récupération WorldNewsAPI, citations URL par affirmation, abstention si les sources sont insuffisantes, évaluation RAG reproductible | Au moins 95 % des affirmations vérifiables sourcées et moins de 2 % d’affirmations non corroborées |
| Fraîcheur des informations | Mesurer l’âge médian des articles présentés sur 100 demandes temporelles | Filtrer et classer les articles selon date de publication et date de mise à jour, afficher horodatage et fuseau | Âge médian inférieur à 24 h pour une demande « dernières actualités » |
| Latence | Enregistrer p50/p95 de 500 requêtes de bout en bout en environnement de préproduction | Appels parallèles aux sources, timeout borné, cache par requête et fenêtre de fraîcheur, streaming de réponse | p95 inférieur à 8 s pour une réponse sourcée, hors pannes externes |
| Disponibilité et coûts | Suivre le taux d’erreur et le coût par 1 000 requêtes sur un test de charge de 30 min | Retries bornés avec jitter, circuit breaker, limites de tokens, modèle léger pour les tâches de classement | Au moins 99,5 % de requêtes servies et coût plafonné sous un budget défini avant lancement |
| Qualité des synthèses | Faire noter 100 synthèses à l’aveugle sur pertinence, neutralité et diversité des sources | Rubrique de notation éditoriale, détection de doublons, couverture de sources contradictoires, revue humaine des cas limites | Note moyenne d’au moins 4/5, aucune source unique au-delà de 50 % des citations |

## Protocole d’évaluation

1. Constituer un corpus versionné de questions datées, d’articles de référence, de réponses attendues et de sujets à risque éditorial.
2. Exécuter les versions de prompts et de modèles sur les mêmes données, puis publier exactitude, latence p50/p95, taux d’abstention et coût par requête.
3. Faire annoter à l’aveugle les réponses par deux évaluateurs, arbitrer les désaccords et suivre les scores par sujet et par source.
4. Bloquer un déploiement si l’exactitude baisse de plus de 2 points, si le p95 dépasse l’objectif ou si une réponse contient des citations non vérifiables.
5. Surveiller en production les réponses signalées, les erreurs WorldNewsAPI, la fraîcheur des sources et le coût, sans conserver de données personnelles au-delà de la politique définie.

Les seuils sont des objectifs, pas des résultats mesurés. Ils devront être adaptés après constitution du corpus et validation éditoriale.