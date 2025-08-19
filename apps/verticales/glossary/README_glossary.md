---

# 📘 README — App `glossary`

> Ce fichier respecte les conventions décrites dans [`README Brief Technique.md`](../README Brief Technique.md), situé à la racine du dossier `apps/`.  
> Il décrit l’objectif, le type, les composants, l’intégration, et les responsabilités internes de l’app.

---

## 🧩 Type d’app

| Type         | Description                                                                 |
|--------------|------------------------------------------------------------------------------|
| Transversale | Fournit un service technique réutilisable par plusieurs apps                |
| Verticale    | App métier qui utilise les services des apps transverses                    |

> Cette app est de type : **`verticale`**  
> Elle dépend des apps transverses suivantes :
> - `language` : pour la traduction automatique
> - `seo` : pour l’injection des champs SEO
> - `faiss_pgvector` : pour la vectorisation et la recherche sémantique

---

## 🔗 Dépendances

| App              | Rôle dans `glossary`                                                                 |
|------------------|--------------------------------------------------------------------------------------|
| `language`       | Traduction automatique des champs multilingues (`labels`, `definition`, `seo`)      |
| `seo`            | Génération et validation des blocs SEO multilingues                                 |
| `faiss_pgvector` | Encodage des définitions en vecteurs + recherche sémantique via FAISS               |

```python
## 📦 Imports nécessaires

from apps.language.utils import get_active_langs
from seo.models import SEOblock
from faiss_pgvector.embeddings import encode_text
```

---

## 🎯 Objectif

L’app `glossary` structure les savoir-faire industriels sous forme de nœuds typés et gouvernés :  
**Métier**, **Opération**, **Variante**.

Les nœuds sont reliés entre eux par des liens multiples (`parents`), mais chaque **variante** est engagée dans un **path canonique unique** du type :

```
Métier → Opération → Variante
```

Ce path est :
- Typé et gouverné
- Stable dans le temps
- Utilisé comme clé de matching IA pour l’enrichissement, la vectorisation et la recherche

> Il ne s’agit pas d’une hiérarchie stricte : les liens entre nœuds sont multiples, mais le path canonique est unique par variante.

---

## 🧱 Modèle principal

### `GlossaryNode`

- Représente un terme ou concept du glossaire
- Contient les champs principaux : `title`, `definition`, `seo`, `embedding`, `alerts`
- Est enrichi automatiquement via IA (définition, SEO, vecteur)

```python
class GlossaryNode(models.Model):
    glossary_id = models.CharField(...)       # identifiant canonique
    node_id = models.CharField(...)           # slug UX
    type = models.CharField(...)              # métier / opération / variante
    labels = models.JSONField(...)            # noms multilingues
    definition = models.JSONField(...)        # contenu multilingue
    seo = models.JSONField(...)               # SEO multilingue
    embedding = VectorField(dim=384, ...)     # vecteur sémantique
    alerts = models.JSONField(default=list)   # alertes IA
    parent = models.ForeignKey(...)           # lien unique vers le parent
    ...
```

> Les champs traduisibles sont synchronisés avec le modèle `TranslatableKey` de l’app `language`.

---

## 🧠 Logique métier

- Les nœuds sont typés (`métier`, `opération`, `variante`) et gouvernés
- Chaque variante est engagée dans un **path canonique unique** (`métier → opération → variante`)
- Ce path est utilisé pour :
  - L’enrichissement sémantique via Mistral API
  - Le calcul d’embedding via `faiss_pgvector`
  - La recherche sémantique via FAISS
- Les champs multilingues sont traduits automatiquement via `language`
- Les alertes IA signalent les incohérences ou enrichissements à valider
- La synchronisation avec `TranslatableKey` est assurée dans `services.py` ou `utils.py`

---

## 🧭 Règles de structuration

```python
if t == GlossaryType.METIER and self.parent is not None:
    raise ValidationError("Un 'métier' ne doit pas avoir de parent.")
if t == GlossaryType.OPERATION and self.parent.type != GlossaryType.METIER:
    raise ValidationError("Une 'opération' doit avoir un parent de type 'métier'.")
if t == GlossaryType.VARIANTE and self.parent.type != GlossaryType.OPERATION:
    raise ValidationError("Une 'variante' doit avoir un parent de type 'opération'.")
```

---

## 🔌 Intégrations externes

- **Mistral API** : enrichissement sémantique des définitions
- **Societe.com API** : (optionnel) récupération de données d’entreprise

---

## ⏱ Tâches Celery

- Recalcul des embeddings
- Mise à jour de l’index FAISS
- Traduction en batch
- Enrichissement automatique

---

## 🧪 Tests

- Localisation : `apps/glossary/tests/`
- Framework : `pytest`
- Génération : `factory_boy`
- Couverture : `pytest-cov`

---

## 📂 Structure interne de l’app

```plaintext
glossary/
├── apps.py                         # Configuration Django de l’app
├── models.py                       # GlossaryNode, SEO, embedding
├── services.py                     # Logique métier : enrichissement, traduction, vectorisation
├── utils.py                        # Helpers SEO, JSON, traduction
├── tasks.py                        # Tâches IA, FAISS, traduction
├── admin.py                        # Interface d’administration, alertes IA
├── forms.py                        # Formulaires multilingues, SEO
├── serializers.py                  # API, validation, lecture seule sur embedding
├── views.py                        # Endpoints API
├── urls.py                         # Routage local
├── permissions.py                  # Règles d’accès
├── signals.py                      # Réactions aux événements (optionnel)
├── management/commands/            # Commandes CLI pour enrichir les nœuds
├── templates/admin/glossary/       # Assistant de traduction IA
├── static/glossary/                # JS/CSS spécifique à l’admin
├── specific/fixtures/              # Fixtures ou scripts non partagés
└── tests/                          # Tests unitaires
```

---

## 🧭 Règles de structuration

- Les champs traduisibles sont synchronisés avec `language`
- Le SEO est géré via `seo` et validé dans le formulaire admin
- Les embeddings sont générés via `faiss_pgvector` et stockés en base
- Les recherches sémantiques sont déléguées à FAISS
- Les enrichissements IA sont orchestrés via tâches Celery et commandes
- L’app respecte l’ordre de développement défini dans [`README Brief Technique.md`](../README Brief Technique.md)
- Les responsabilités des fichiers sont strictement délimitées
- Toute logique métier complexe est placée dans `services.py`
- Les appels aux apps transverses sont explicites et documentés
- Les champs traduisibles sont synchronisés via `TranslatableKey`, avec la logique placée dans `services.py` ou `utils.py` selon le besoin
- Aucun fichier inutile ne doit être présent

---