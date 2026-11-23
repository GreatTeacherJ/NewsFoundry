# Déploiement 

(Pour plus d'information voir [`README`](../README.md#deploiement)

- DB + Backend via Railway : [**`https://newsfoundry-production-74e5dc89.up.railway.app`**](https://newsfoundry-production-74e5dc89.up.railway.app)
- EndPoint : [**`https://newsfoundry-production-74e5dc89.up.railway.app/docs`**](https://newsfoundry-production-74e5dc89.up.railway.app/docs)
- Frontend via Vercel : [**`news-foundry-seven.vercel.app`**](news-foundry-seven.vercel.app)

# Réduire les tokens des appels LLM

## TL;DR

Sur une même conversation, le prompt passe d’environ **2 500 tokens** au premier tour à près de **5 800 tokens** sur des questions sans rapport avec les actualités. Le bloc « Données déjà récupérées » est réinjecté systématiquement, et le retour brut de `search-news` atteint **8 216 tokens**. Priorités : n’ajouter les données que lorsqu’elles sont utiles, compacter les résultats d’outils et borner l’historique. Les cibles de gain restent à valider par mesure.

## 1. Constat chiffré

Mesures observées dans l’ordre chronologique sur une même conversation. Le retour de l’outil est présenté comme un événement distinct.

| Événement / requête | Type / contexte | Tokens | Durée |
|---|---|---:|---:|
| « bonjour » | Historique vide | 2 511 | 1,2 s |
| « deux actualités France sport » | `search-news` | 2 573 | 2,1 s |
| Retour de `search-news` | JSON brut (`id`, `title`…) | 8 216 | 2,1 s |
| « deux actualités mondial sport » | Conversation poursuivie | 5 341 | 3,7 s |
| « revue de presse » | `reviews` | 6 143 | 5,9 s |
| « est-ce que tu me trouves beau » | Hors sujet actualités | 5 757 | 1,4 s |
| « quel temps il fait » | Hors sujet actualités | 5 860 | 1,7 s |
| « donner une nouvelle actualité » | Demande d’actualité | 5 991 | 2,0 s |

Trois observations :

1. **Coût fixe élevé :** environ 2 500 tokens dès « bonjour », même avec un historique vide. Le prompt système, les définitions d’outils et le formatage sont à examiner ; les mesures seules ne permettent pas d’isoler leur contribution.
2. **Contexte jamais purgé :** le bloc « Données déjà récupérées » est ajouté au `user_prompt` à chaque appel suivant, y compris hors sujet. Les questions hors sujet mesurées autour de 5 800 tokens représentent environ **2,3×** le premier appel à 2 511 tokens.
3. **Pic au retour d’outil :** le JSON brut de `search-news` atteint **8 216 tokens**, ce qui suggère que des champs ou du contenu volumineux sont transmis sans projection préalable.

## 2. Problème

- **Coût :** le même contexte récupéré est retokenisé et potentiellement refacturé à chaque requête.
- **Latence :** un prompt plus long peut augmenter le temps de traitement ; les durées mesurées varient aussi selon le modèle, les outils et la charge.
- **Dilution du contexte :** des actualités obsolètes ou non pertinentes concurrencent la requête courante et peuvent nuire à la pertinence.
- **Croissance avec la conversation :** l’historique et les retours d’outils accumulés augmentent le volume si aucune limite ou synthèse n’est appliquée.

## 3. Axes d’amélioration

### A. Injecter les données récupérées uniquement si elles sont utiles

**Principe :** déterminer l’intention avant de construire le prompt. Trois options, de la plus simple à la plus souple :

- **Règles / mots-clés :** repérer des termes comme « actualité », « news » ou « revue de presse ».
- **Petit appel LLM de classification :** retourner une catégorie structurée (`news`, `general`, etc.) et n’ajouter le contexte que pour les catégories pertinentes.
- **Outil à la demande `get_retrieved_news` :** exposer les données comme outil afin que le modèle les demande au besoin, au lieu de les joindre à chaque appel.

**Pourquoi ça marche :** les questions sans lien avec les actualités ne paient plus le coût du bloc récupéré. Les données restent disponibles quand une demande d’actualité les nécessite.

**Compromis / limites :** les règles sont peu coûteuses et rapides mais peuvent manquer des formulations implicites. Un appel de classification augmente la latence et ajoute un coût. L’outil à la demande dépend de la décision du modèle et du bon routage de l’outil ; prévoir un repli contrôlé.

### B. Compresser les résultats d’outils

**Principe :** convertir les réponses en une représentation minimale : projeter les champs réellement utiles (par exemple titre, résumé, source, date, URL), limiter le nombre de résultats et tronquer les champs longs. Éviter de renvoyer tout le JSON si le modèle n’en a pas besoin.

**Pourquoi ça marche :** les identifiants techniques, métadonnées et champs inutilisés ne prennent plus de place dans le contexte. Cela cible particulièrement le pic constaté au retour de `search-news`.

**Compromis / limites :** une projection ou une troncature trop stricte peut supprimer une date, une nuance ou un élément utile à une revue de presse. Définir les champs selon les usages et vérifier la qualité des réponses.

### C. Fenêtre glissante et résumé de l’historique

**Principe :** conserver les derniers messages dans une fenêtre de taille bornée. Si le fil doit garder des éléments plus anciens, les condenser en un résumé compact, mis à jour à intervalles définis.

**Pourquoi ça marche :** la taille du prompt ne croît plus sans limite avec le nombre de tours ; les échanges récents restent prioritaires.

**Compromis / limites :** un résumé peut perdre des contraintes, préférences ou faits importants. Une fenêtre trop courte peut rendre les réponses incohérentes. Préserver séparément les faits durables et tester sur des conversations longues.

### D. Optimiser le prompt système et examiner le prompt caching

**Principe :** mesurer les tokens du prompt système, des définitions d’outils, de l’historique et des résultats séparément. Supprimer les instructions redondantes sans retirer les règles nécessaires. Placer les éléments stables dans un préfixe stable pour favoriser le caching, si le fournisseur le prend en charge.

**Pourquoi ça marche :** le coût de base d’environ 2 500 tokens est présent dès le premier appel ; réduire les éléments fixes bénéficie à tous les tours. Le caching peut réduire le coût effectif et parfois la latence.

**Compromis / limites :** simplifier les consignes peut dégrader la qualité ou le respect des règles. Le prompt caching est **dépendant du fournisseur** : éligibilité, durée, granularité et tarification varient et sont à vérifier dans sa documentation et ses métriques. Il ne réduit pas nécessairement les tokens d’entrée affichés ; distinguer tokens envoyés, tokens mis en cache et tokens facturés.

## 4. Exemple d’implémentation Python

Exemple générique et autonome, illustratif d’un backend Python/FastAPI ; il ne prétend pas décrire le code réel du dépôt. Les clés de messages (`role`, `content`) sont un format générique à adapter au SDK utilisé. `classify_intent` est volontairement rudimentaire : en production, compléter les règles, utiliser un classificateur ou appeler les données au besoin.

```python
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

Message = dict[str, str]
NewsItem = Mapping[str, object]


def _normalize(text: str) -> str:
    """Normalize text for accent-insensitive keyword matching."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def classify_intent(query: str) -> str:
    """Return 'news' when the query appears to concern news; otherwise 'general'."""
    normalized = _normalize(query)
    keywords = (
        "actualite", "actualites", "actu", "news", "presse", "headline",
        "headlines", "revue de presse",
    )
    # Match whole words so a keyword inside an unrelated word is not enough.
    if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
        return "news"
    return "general"


def compact_news(
    results: Sequence[NewsItem],
    *,
    max_items: int = 4,
    max_chars: int = 1600,
    max_summary_chars: int = 350,
) -> str:
    """Keep a bounded, readable projection of retrieved news results."""
    if max_items <= 0 or max_chars <= 0 or max_summary_chars < 0:
        return ""

    lines: list[str] = []
    for result in results[:max_items]:
        title = str(result.get("title", "")).strip()
        summary_value = result.get("summary", result.get("description", ""))
        summary = str(summary_value).strip()[:max_summary_chars]
        source = str(result.get("source", "")).strip()
        date = str(result.get("date", "")).strip()

        # Keep only fields useful for identifying and summarizing a story.
        fields = [value for value in (title, summary, source, date) if value]
        if fields:
            lines.append("- " + " | ".join(fields))

    return "\n".join(lines)[:max_chars]


def trim_history(
    history: Sequence[Mapping[str, str]],
    *,
    max_messages: int = 8,
) -> list[Message]:
    """Return at most the newest max_messages, copying each message."""
    if max_messages <= 0:
        return []
    return [dict(message) for message in history[-max_messages:]]


def build_prompt(
    system_prompt: str,
    history: Sequence[Mapping[str, str]],
    query: str,
    retrieved_news: Sequence[NewsItem] = (),
    *,
    max_history: int = 8,
) -> list[Message]:
    """Build a bounded chat prompt and attach compact news only when relevant."""
    messages: list[Message] = [{"role": "system", "content": system_prompt}]
    intent = classify_intent(query)

    if intent == "news" and retrieved_news:
        news_context = compact_news(retrieved_news)
        if news_context:
            # Attach retrieved context to the current request, not every turn.
            messages.append({
                "role": "system",
                "content": "Données déjà récupérées :\n" + news_context,
            })

    messages.extend(trim_history(history, max_messages=max_history))
    messages.append({"role": "user", "content": query})
    return messages


if __name__ == "__main__":
    # Example data only; adapt fields and limits to the actual tool response.
    system = "Tu es un assistant utile."
    old_news = [{
        "id": "n-1",
        "title": "Exemple de titre",
        "summary": "Résumé bref de l’article.",
        "source": "Exemple",
        "raw_payload": "Champ volumineux ignoré",
    }]
    history: list[Message] = []

    before_prompt = [
        {"role": "system", "content": system + "\n\nDonnées déjà récupérées :\n" + str(old_news)},
        {"role": "user", "content": "Est-ce que tu me trouves beau ?"},
    ]
    after_prompt = build_prompt(
        system,
        history,
        "Est-ce que tu me trouves beau ?",
        old_news,
    )
    print("Avant :", before_prompt)
    print("Après :", after_prompt)
```

**Avant (principe observé) :** le prompt inclut systématiquement « Données déjà récupérées » et peut transmettre les objets complets, même pour « Est-ce que tu me trouves beau ? ».

**Après (avec l’exemple) :** `classify_intent` classe cette question en `general`, donc `build_prompt` ne joint pas les actualités. Pour une demande telle que « revue de presse », il joint seulement la projection bornée de `compact_news`. Le format exact de stockage et de transmission des messages reste à adapter à l’intégration réelle.

## 5. Gain attendu — estimation à valider

Cible indicative pour un appel comparable actuellement autour de 5 800 tokens, lorsque ce volume inclut le contexte d’actualités hors sujet. Ce n’est pas une garantie : les mesures dépendent du prompt, de l’historique, des résultats d’outils, du modèle et du tokenizer.

| Cas comparable | Avant | Après (cible estimative) | Réduction estimée |
|---|---:|---:|---:|
| Requête hors sujet avec données récupérées injectées | ~5 800 tokens observés | ~2 500 tokens estimés | ~3 300 tokens, soit ≈55–57 % |

La cible suppose l’omission du bloc hors sujet et une taille maîtrisée de l’historique. Les demandes qui utilisent réellement des actualités conserveront un coût supplémentaire, atténué par la compression. **Valider cette estimation par rejeu et mesure fournisseur.**

## 6. Plan de validation et de mesure

1. Rejouer la même conversation, dans le même ordre, avec les mêmes paramètres de modèle et les mêmes réponses d’outils.
2. Comparer les tokens **par appel** avant/après, y compris le retour d’outil. Si disponibles, séparer prompt système, outils, historique, contexte récupéré et réponse.
3. Ajouter des tests unitaires pour `classify_intent` (requêtes d’actualité et hors sujet, avec accents), `compact_news` (champs absents et limites), `trim_history` (historique vide et dépassement de fenêtre) et `build_prompt` (contexte présent ou absent selon l’intention).
4. Vérifier explicitement que la qualité des réponses de `reviews` / revue de presse ne régresse pas : pertinence, couverture des éléments, dates et sources utiles.
5. Suivre aussi la latence et le coût des appels éventuels de classification. Utiliser les métriques d’usage du fournisseur pour les tokens réels ; une estimation par caractères ne remplace pas le tokenizer du modèle.

## 7. Pièges et nuances

- Le routage par mots-clés peut rater une intention exprimée indirectement ou déclencher à tort sur un terme ambigu ; mesurer ses faux négatifs et faux positifs.
- Un résumé d’historique peut perdre une information importante. Conserver les contraintes durables dans une mémoire structurée et prévoir un moyen de retrouver les données sources.
- Un appel LLM supplémentaire de classification peut réduire les tokens de l’appel principal mais augmenter la latence et le coût total ; comparer le coût global, pas seulement un appel isolé.
- La durée n’est pas proportionnelle aux tokens dans tous les cas. Mesurer tokens, latence, coût et qualité ensemble.
