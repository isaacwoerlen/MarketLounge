Voici le README complet pour l'app `seo`.

---

# 📘 README — App `seo`

> Ce fichier respecte les conventions décrites dans [`README Brief Technique.md`](../README Brief Technique.md), situé à la racine du dossier `apps/`.  
> Il décrit l’objectif, le type, les composants, l’intégration, et les responsabilités internes de l’app.

---

## 🧩 Type d’app

| Type         | Description                                                                 |
|--------------|------------------------------------------------------------------------------|
| Transversale | Fournit un service SEO/OG réutilisable par toutes les apps métier           |

> Cette app est de type : **`transversale`**  
> Elle est utilisée par toutes les apps métier (ex: `glossary`, `company`, `market`, `dictionary`) pour automatiser et centraliser la gestion du SEO/OG.

---

## 🎯 Objectif

L’app `seo` est conçue pour :
- Centraliser la gestion des métadonnées SEO et Open Graph
- Automatiser leur génération multilingue
- Offrir une interface d’édition via l’admin Django
- Éviter de coder manuellement le SEO dans chaque app métier

---

## 🧱 Modèles principaux

### `SeoBlock`

- Représente un bloc SEO/OG pour une entité donnée (ex: une fiche `Company`, un terme `Glossary`)
- Contient les champs standards : `title`, `description`, `image`, `keywords`, etc.
- Est lié à un `TranslatableKey` pour chaque champ

```python
class SeoBlock(models.Model):
    scope = models.CharField(...)       # ex: "company", "glossary"
    object_id = models.UUIDField(...)   # identifiant de l’objet métier
    title_key = models.ForeignKey(...)  # vers TranslatableKey
    description_key = models.ForeignKey(...)
    image_url = models.URLField(...)
    keywords = models.JSONField(...)
```

### `SeoTemplate`

- Permet de définir des modèles de SEO dynamiques
- Utilise des placeholders pour générer automatiquement les titres/descriptions

```python
class SeoTemplate(models.Model):
    scope = models.CharField(...)       # ex: "market"
    title_template = models.TextField(...)     # ex: "Découvrez {{ name }} sur {{ region }}"
    description_template = models.TextField(...)
    is_active = models.BooleanField(...)
```

---

## 🔌 Intégrations externes

- **App `language`** : utilisée pour traduire les champs SEO/OG via Mistral
- **Admin Django** : permet de visualiser, éditer et valider les blocs SEO
- **Apps métier** : consomment les blocs SEO via des mixins ou des serializers

---

## ⏱ Tâches Celery

- Génération automatique des blocs SEO pour les objets métier
- Traduction multilingue des champs SEO via `TranslationJob`
- Validation des longueurs SEO (title ≤ 60, description ≤ 160)

---

## 🧠 Logique métier

- Chaque objet métier peut déclarer un `SeoBlock` via un mixin
- Les champs SEO sont traduits automatiquement via `language`
- Les templates dynamiques permettent de générer des SEO cohérents
- Les validations SEO sont intégrées dans le modèle `Translation`

---

## 🧪 Tests

- Localisation : `apps/seo/tests/`
- Framework : `pytest`
- Génération : `factory_boy`
- Couverture : `pytest-cov`

---

## 📂 Structure interne de l’app

```plaintext
seo/
├── __init__.py
├── apps.py
├── models.py
├── admin.py
├── serializers.py
├── views.py
├── services.py
├── utils.py
├── urls.py
├── tasks.py
├── signals.py
├── permissions.py
├── templates/
│   └── admin/
│       └── seo/
│           └── seo_block.html
├── static/
│   └── seo/
│       ├── seo_admin.js
│       └── seo_admin.css
├── specific/
│   └── fixtures/
│       └── seo_templates.json
└── tests/
    ├── test_models.py
    ├── test_services.py
    ├── test_tasks.py
    ├── test_admin.py
    ├── factories.py
    └── conftest.py
```

---

## 🧭 Règles de structuration

- L’app respecte l’ordre de développement défini dans [`README Brief Technique.md`](../README Brief Technique.md)
- Les blocs SEO sont liés à des clés traduisibles (`TranslatableKey`)
- Les templates SEO sont versionnés et validables
- Les validations SEO sont centralisées dans `language.utils.validate_seo_lengths()`
- Les apps métier n’ont plus besoin de coder manuellement le SEO

---

