---

## ✅ Objectifs de `README_app_exemple.md`

- 📚 Sert de **template** pour tous les futurs README d’apps
- 🧩 Rappelle les **conventions d’arborescence et de développement** définies dans `README Brief Technique.md`
- 🧠 Clarifie les rôles des fichiers internes (`views.py`, `services.py`, etc.)
- 🔄 Encourage la modularité et la réutilisabilité

---

## 🏗️ Structure `README_app_exemple.md`

---

# 📘 README — App `nom_de_l_app`

> Ce fichier respecte les conventions décrites dans [`README Brief Technique.md`](../README Brief Technique.md), situé à la racine du dossier `apps/`.  
> Il décrit l’objectif, le type, les composants, l’intégration, et les responsabilités internes de l’app.

---

## 🧩 Type d’app

| Type         | Description                                                                 |
|--------------|------------------------------------------------------------------------------|
| Transversale | Fournit un service technique réutilisable par plusieurs apps (ex: `language`, `seo`, `faiss_pgvector`) |
| Verticale    | App métier qui utilise les services des apps transverses (ex: `glossary`, `market`) |

> Cette app est de type : **`verticale`**  
> Elle dépend des apps transverses suivantes :
> - `language` : pour la traduction automatique
> - `seo` : pour l’injection des champs SEO
> - `faiss_pgvector` : pour la vectorisation et la recherche sémantique

---

## 📦 Imports nécessaires

```python
from apps.language.utils import get_active_langs
from seo.models import SEOblock
from faiss_pgvector.embeddings import encode_text
```

---

## 🎯 Objectif

Décrire en un paragraphe clair le rôle métier ou technique de l’app.  
Exemple : “Le Glossaire constitue la colonne vertébrale du projet.
Il définit une hiérarchie rigide et gouvernée des savoir-faire industriels :
Métier → Opération → Variante.
Chaque nœud du Glossaire représente une unité stable de connaissance métier.
Il est la source de vérité pour la structuration des concepts activables.
”

---

## 🧱 Modèle(s) principal(aux)

Décrire les modèles clés et leur rôle.  
Inclure un extrait de code si pertinent :

```python
class Term(models.Model):
    name = models.CharField(...)
    definition = models.TextField(...)
    seo = SEOblock()
    embedding = VectorField(dim=384)

    def save(self, *args, **kwargs):
        translate_fields(self, fields=["name", "definition"])
        self.embedding = encode_text(self.definition)
        super().save(*args, **kwargs)
```

---

## 🧠 Logique métier

- Encodage des définitions via `sentence-transformers`
- Stockage des vecteurs dans PostgreSQL (`pgvector`)
- Recherche sémantique via FAISS
- Enrichissement des définitions via Mistral API
- Traduction automatique des champs via `language`

---

## 🔌 Intégrations externes

- **Mistral API** : enrichissement sémantique
- **Societe.com API** : récupération des données d’entreprise (si applicable)

---

## ⏱ Tâches Celery

- Recalcul des embeddings
- Mise à jour de l’index FAISS
- Traduction en batch
- Enrichissement automatique

---

## 🧪 Tests

- Localisation : `apps/<app>/tests/`
- Framework : `pytest`
- Génération : `factory_boy`
- Couverture : `pytest-cov`

---

## 🧱 Structure interne de l’app

Chaque app doit respecter **la même dénomination des fichiers** et **le rôle associé à chacun**, même si elle n’utilise que les fichiers nécessaires à sa logique propre.  
Aucun fichier inutile ne doit être présent.

```plaintext
app_exemple/
├── __init__.py                     # Initialisation du module Python
├── apps.py                         # [0] Configuration Django de l’app
├── models.py                       # [1] Définir les modèles de données
├── admin.py                        # [6] Interface d’administration Django
├── forms.py                        # [7] Formulaires personnalisés (si besoin)
├── serializers.py                  # [2] Sérialisation des modèles pour l’API ou l’IA
├── views.py                        # [2] Contrôleurs (API ou vues HTML) — logique de présentation
├── services.py                     # [3] Logique métier réutilisable (vectorisation, enrichissement IA, etc.)
├── utils.py                        # [3] Fonctions utilitaires non métier
├── urls.py                         # [5] Routage local de l’app
├── tasks.py                        # [8] Tâches asynchrones (ex: IA, batch, Celery)
├── signals.py                      # [9] Réactions aux événements (save, delete, etc.)
├── permissions.py                  # [10] Règles d’accès granulaires
├── management/
│   └── commands/
│       └── generate_app_exemple.py # [11] Commandes CLI Django personnalisées
├── templates/
│   └── admin/
│       └── app_exemple/
│           └── custom_action.html  # [12] Templates HTML spécifiques à l’admin
├── static/
│   └── app_exemple/
│       ├── app_exemple_admin.js    # [13] JS spécifique à l’admin
│       └── app_exemple_admin.css   # [14] CSS spécifique à l’admin
├── specific/
│   └── fixtures/
│       └── app_exemple.json        # [15] Fixtures ou scripts non partagés
└── tests/                          # [16] Tests unitaires avec `pytest`
```

---

## 🧭 Règles de structuration

- L’app doit respecter l’ordre de développement défini dans [`README Brief Technique.md`](../README Brief Technique.md)
- Les responsabilités des fichiers sont strictement délimitées (voir tableau des frontières)
- Toute logique métier complexe doit être placée dans `services.py` et non dans `views.py`, `tasks.py`, ou `signals.py`
- Les appels aux apps transverses doivent être explicites et documentés
- Chaque fichier a un **rôle précis** et ne doit pas être détourné.
- Les noms de fichiers sont **standardisés** pour faciliter la navigation et la maintenance.
- Une app n’inclut que les fichiers **strictement nécessaires** à sa logique métier ou technique.

---