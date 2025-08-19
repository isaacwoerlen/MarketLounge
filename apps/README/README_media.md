---

# 📘 README — App `media`

> Ce fichier respecte les conventions décrites dans [`README Brief Technique.md`](../README Brief Technique.md), situé à la racine du dossier `apps/`.  
> Il décrit l’objectif, le type, les composants, l’intégration, et les responsabilités internes de l’app.

---

## 🧩 Type d’app

| Type         | Description                                                                 |
|--------------|------------------------------------------------------------------------------|
| Transversale | Fournit un service technique réutilisable par plusieurs apps (`glossary`, `market`, etc.) |
| Verticale    | App métier qui utilise les services des apps transverses                    |

> Cette app est de type : **`transversale`**  
> Elle est utilisée par les apps verticales pour gérer les fichiers multimédias (images, vidéos, documents).

---

## 📦 Imports nécessaires

```python
from apps.language.utils import get_active_langs
from seo.models import SEOblock
from faiss_pgvector.embeddings import encode_text
```

---

## 🎯 Objectif

L’app `media` centralise la gestion des fichiers multimédias utilisés dans les différentes apps métier.  
Elle permet d’uploader, stocker, enrichir, traduire et réutiliser des contenus visuels (images, vidéos, documents) dans une logique transverse.  
Elle offre des services d’optimisation, de vectorisation, et d’intégration SEO multilingue.

---

## 🧱 Modèle principal

### `Media`

```python
class Media(models.Model):
    file = models.FileField(upload_to="media/")
    type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    alt_text = models.CharField(max_length=255)
    caption = models.TextField(blank=True)
    copyright = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    embedding = VectorField(dim=384, null=True, blank=True)
```

> Les champs `alt_text` et `caption` sont traduisibles et synchronisés avec le modèle `TranslatableKey` de l’app `language`.

---

## 🧠 Logique métier

- Traduction automatique des champs `alt_text` et `caption` via `language`
- Synchronisation avec `TranslatableKey` dans `services.py` ou `utils.py`
- Génération de vecteurs sémantiques à partir des légendes (`caption`)
- Stockage des vecteurs dans PostgreSQL (`pgvector`)
- Recherche sémantique sur les médias via FAISS
- Enrichissement SEO des médias via `seo`
- Génération de thumbnails et resize automatique
- Gestion des droits d’auteur et licences

---

## 🔌 Intégrations externes

- **Mistral API** : enrichissement des légendes et alt text
- **Cloudflare Images / S3** : stockage distant et CDN
- **OCR API** : extraction de texte depuis les documents (PDF, images)

---

## ⏱ Tâches Celery

- Recalcul des embeddings pour les légendes
- Traduction en batch des métadonnées
- Génération automatique de thumbnails
- Enrichissement SEO des médias

---

## 🧪 Tests

- Localisation : `apps/media/tests/`
- Framework : `pytest`
- Génération : `factory_boy`
- Couverture : `pytest-cov`

---

## 📂 Structure interne de l’app

```plaintext
media/
├── __init__.py
├── apps.py                         # [0] Configuration Django de l’app
├── models.py                       # [1] Modèle Media, métadonnées, vecteurs
├── admin.py                        # [6] Interface d’administration, preview, SEO
├── forms.py                        # [7] Formulaires d’upload et de métadonnées
├── serializers.py                  # [2] API pour les médias
├── views.py                        # [2] Endpoints d’upload, preview, recherche
├── services.py                     # [3] Resize, vectorisation, enrichissement
├── utils.py                        # [3] Helpers de traduction, SEO, format
├── urls.py                         # [5] Routage local
├── tasks.py                        # [8] Tâches Celery : enrichissement, traduction
├── signals.py                      # [9] Sync des traductions à la sauvegarde
├── permissions.py                  # [10] Droits d’accès aux fichiers
├── management/
│   └── commands/
│       └── enrich_media.py         # [11] Commande CLI pour enrichir les médias
├── templates/
│   └── admin/
│       └── media/
│           └── preview.html        # [12] Preview admin
├── static/
│   └── media/
│       ├── media_admin.js          # [13] JS spécifique à l’admin
│       └── media_admin.css         # [14] CSS spécifique à l’admin
├── specific/
│   └── fixtures/
│       └── media_samples.json      # [15] Fixtures ou scripts non partagés
└── tests/                          # [16] Tests unitaires
```

---

## 🧭 Règles de structuration

- Les champs traduisibles sont synchronisés avec `language`
- Le SEO est enrichi via `seo` et validé dans le formulaire admin
- Les embeddings sont générés via `faiss_pgvector` et stockés en base
- Les recherches sémantiques sont déléguées à FAISS
- Les enrichissements IA sont orchestrés via tâches Celery et commandes
- L’app respecte l’ordre de développement défini dans [`README Brief Technique.md`](../README Brief Technique.md)
- Les responsabilités des fichiers sont strictement délimitées
- Toute logique métier complexe est placée dans `services.py`
- Les appels aux apps transverses sont explicites et documentés
- Aucun fichier inutile ne doit être présent

---

