📘 README — Apps MarketLounge
Ce répertoire contient toutes les applications Django du projet MarketLounge. Certaines apps sont verticales (spécifiques à un domaine métier, ex. : glossary, market, matching, dico, curation), tandis que d’autres sont transverses (services techniques réutilisables, ex. : language, seo).  
Ce document est aligné avec README_Architecture du Lounge_V07.md, qui détaille les aspects fonctionnels et flux (offline → runtime → apprentissage). Les rôles des apps respectent les principes no-overlap : chaque app est dédiée à un rôle unique (ex. : dico pour génération concepts offline, matching pour matching runtime hybrid avec FAISS/pgvector/Redis).
🧭 Conventions de développement

Chaque app possède un fichier README.md décrivant son objectif, modèles, vues, tâches, etc.
Apps transverses (language, seo) ne dépendent pas des verticales.
Apps verticales consomment transverses via mixins, helpers ou modèles abstraits.
Tests organisés par app dans apps/<app>/tests/ avec pytest.
Fichiers respectent structure définie dans app_exemple/.

🧩 Apps transverses
🔤 language

Objectif : Traduction automatique des champs via Mistral API.
Fonctionnement : Centralise langues activées ; traduit champs marqués ; évite duplication (ex. : label_fr).
Intégration : Importer mixins/fonctions dans modèles ; utiliser helpers dans vues/serializers.

📈 seo

Objectif : Injection champs SEO/OpenGraph dans modèles.
Fonctionnement : Utilise SEOblock mixin ; traduit via language ; génère balises meta.
Intégration : Ajouter SEOblock dans modèles ; utiliser helpers dans templates/serializers.

🧠 LLM_ai

Objectif : Enrichissements sémantiques via LLM (Mistral, OpenAI).
Fonctionnement : Génère résumés, suggestions ; expose API interne.
Intégration : Utiliser helpers dans services.py/tasks.py des verticales.

📸 media

Objectif : Gestion multimédias (images, vidéos, documents).
Fonctionnement : Stockage/métadonnées ; associe à contenus.
Intégration : Importer modèles/helpers pour associer fichiers.

📑 taxonomy

Objectif : Gouvernance types/rôles/structures métier.
Fonctionnement : Définit taxonomies réutilisables (catégories, tags, hiérarchies).
Intégration : Utiliser modèles/helpers pour appliquer taxonomies.

📊 metrics

Objectif : Suivi enrichissements, alertes, usages.
Fonctionnement : Collecte métriques (recherches, IA) ; expose rapports.
Intégration : Importer helpers pour enregistrer métriques.

🔐 permissions

Objectif : Droits d’accès mutualisés.
Fonctionnement : Règles granulaires par rôle/entreprise ; décorateurs/mixins.
Intégration : Appliquer dans views.py/serializers.py.

🛠️ utils_core

Objectif : Fonctions utilitaires transverses (JSON, dates, formats).
Fonctionnement : Centralise helpers techniques sans logique métier.
Intégration : Importer dans verticales/transverses.

🧩 Apps verticales
📖 glossary

Objectif : Structurer savoir-faire industriels (définitions, termes).
Dépendances : language, seo, LLM_ai, media, taxonomy, matching.
Fonctionnement : Gère termes avec définitions, traductions, SEO ; utilise matching pour recherches sémantiques.
Intégration : Modèles avec SEOblock ; traduction via language ; vectorisation via matching.

🏢 company

Objectif : Gérer données entreprise (fiches, SIREN).
Dépendances : language, seo, media, LLM_ai.
Fonctionnement : Intègre via API Societe.com ; enrichit résumés IA.
Intégration : Modèles avec SEOblock ; traduction via language.

🧠 dico

Objectif : Génération offline concepts activables (Dictionnaire Sémantique).
Dépendances : LLM_ai, taxonomy.
Fonctionnement : Parse facettes ; valide via Glossaire ; enrichit statiquement (synonymes, embeddings).
Intégration : Helpers pour matching (usage runtime), curation (validation).

🛒 market

Objectif : Gestion offres/demandes ; analyse marché (tensions, raretés).
Dépendances : language, matching, taxonomy, metrics.
Fonctionnement : Création/recherche offres ; utilise matching pour recommandations ; croise offre/demande.
Intégration : Recherche via matching ; suivi via metrics.

🔍 matching

Objectif : Matching runtime hybrid (lexical + vectoriel) avec vectorisation/recherche sémantique.
Dépendances : LLM_ai, taxonomy.
Fonctionnement : Encode via sentence-transformers ; stocke vecteurs pgvector ; index FAISS (.index) ; rerank via LLM ; cache résultats Redis.
Intégration : Helpers (encode_text, store_vector, search_similar) ; synchronise index via Celery.

🗂️ curation

Objectif : Curation contenus (sélection, validation humaine).
Dépendances : language, seo, media, taxonomy, matching, LLM_ai.
Fonctionnement : Sélectionne/organise contenus ; valide proposals ; enrichit via dico (après validation).
Intégration : Modèles avec SEOblock ; traduction via language ; recherche via matching.

📜 logs

Objectif : Historiser actions, enrichissements, alertes (query_match_log).
Dépendances : metrics, permissions.
Fonctionnement : Enregistre événements ; fournit rapports ; trace request_ID.
Intégration : Enregistrement via signaux/tâches ; feedback à curation.

🚀 activation

Objectif : Activation comptes/onboarding/rôles ; index activations concepts.
Dépendances : permissions, metrics.
Fonctionnement : Flux inscription ; applique rôles ; index activations pour matching.
Intégration : Sécurisation via permissions ; suivi via metrics.

🌐 api

Objectif : Endpoints publics/internes.
Dépendances : language, seo, matching, taxonomy.
Fonctionnement : Expose données verticales via REST ; intègre recherches sémantiques.
Intégration : Serializers/vues pour exposer données.

🧠 Vectorisation & Recherche Sémantique
Gérée par matching :  

Encodage : sentence-transformers.  
Stockage : pgvector PostgreSQL.  
Indexation : FAISS (.index, IVF/HNSW).  
Synchronisation : Celery/commande CLI.  
Cache : Redis pour résultats runtime.

Exemple :  
# apps/verticales/glossary/models.py  
from verticales.matching.services import encode_text, store_vector  

class Term(models.Model):  
    definition = models.TextField()  
    embedding = VectorField(dim=384)  

    def save(self, *args, **kwargs):  
        super().save(*args, **kwargs)  
        vector = encode_text(self.definition)  
        store_vector(self, vector)  

🧪 Intégration dans une App
Exemple avec glossary (utilise language, seo, matching, dico pour concepts) :  
# apps/verticales/glossary/models.py  
from transversales.seo.models import SEOblock  
from transversales.language.utils import translate_fields  
from verticales.matching.services import encode_text, store_vector  
from verticales.dico.services import generate_concept_id  # Ex. pour concept_ID  

class Term(models.Model):  
    name = models.CharField(max_length=255)  
    definition = models.TextField()  
    seo = SEOblock()  
    embedding = VectorField(dim=384)  

    def save(self, *args, **kwargs):  
        translate_fields(self, fields=["name", "definition"])  
        super().save(*args, **kwargs)  
        self.seo.generate_meta_tags(title=self.name, description=self.definition)  
        vector = encode_text(self.definition)  
        store_vector(self, vector)  
        generate_concept_id(self)  # Génération offline via dico  

Structure
MarketLounge/
├── apps/
│   ├── transversales/  ← Services réutilisables
│   │   ├── language/
│   │   ├── seo/
│   │   ├── media/
│   │   ├── taxonomy/
│   │   ├── utils_core/
│   │   ├── metrics/
│   │   ├── permissions/
│   │   └── LLM_ai/
│   ├── verticales/     ← Apps métier
│   │   ├── activation/
│   │   ├── api/
│   │   ├── company/
│   │   ├── glossary/
│   │   ├── logs/
│   │   ├── market/
│   │   ├── matching/   ← Inclut FAISS/pgvector
│   │   ├── dico/
│   │   └── curation/
│   └── README/         ← Modèles README
│       ├── README Brief Technique.md
│       ├── README_app_exemple.md
│       └── README_glossary.md
├── config/             ← Django/Celery config
│   ├── settings.py
│   ├── asgi.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── faiss_index/        ← Index FAISS persistés
├── logs/               ← Logs applicatifs
├── staticfiles/        ← Fichiers statiques
├── venv/               ← Environnement virtuel
├── .env
├── .gitignore
├── check_encoding.py
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── nginx.conf
└── requirements.txt

⚙️ Stack Technique



Composant
Technologie



Backend
Django + REST Framework


Base de données
PostgreSQL + pgvector


Vector DB
FAISS (.index)


UI
Django Templates + htmx


Style
Tailwind CSS (CDN)


Authentification
Django auth


Déploiement
Docker + nginx


IA locale
sentence-transformers


Tâches asynchrones
Celery + django_celery_beat


Cache
Redis (pour résultats matching)


API externe
societe.com


API IA
Mistral API

Stratégie d'Interactions Inter-Apps et Scalabilité
Contexte
L'app language est utilisée exclusivement en interne pour fournir des traductions multilingues (ex. : glossary, market) via un modèle "pull" (appels Python directs). Les interactions HTTP ne sont pas nécessaires actuellement, mais une migration vers HTTP est prévue pour gérer une complexité accrue (ex. : microservices, dashboards internes). FastAPI sera considéré pour les services à haute fréquence (ex. : language, LLM_ai, matching) dans les évolutions futures (V1.1+).
Approche Actuelle : Appels Python Directs

Modèle Pull : Les apps verticales (ex. : glossary, market) appellent directement les services transverses (ex. : language.services.batch_translate_items) via des clients encapsulés (ex. : language_client.py).
Exemple : glossary.models.Term.save() appelle language_client.translate_items pour traduire label ou definition.


Avantages :
Performance : Pas de latence réseau.
Simplicité : Appels Python directs, faciles à déboguer.
Sécurité : Pas d'exposition réseau interne.


Mise en œuvre :
Chaque app appelante a un client (ex. : glossary/services/language_client.py) encapsulant les appels à language.services.
Utilisation de Celery (tasks.py) pour les tâches asynchrones (ex. : traductions, vectorisation).
Admin Django (admin.py, translation_job.html) pour la gestion humaine.
CLI (sync_translations.py) pour la synchronisation batch.

--- README Brief Technique_V02.md (original)
+++ README Brief Technique_V02.md (patched)
@@ -200,6 +200,10 @@
 Stratégie d'Interactions Inter-Apps et Scalabilité
 Contexte
 L'app language est utilisée exclusivement en interne pour fournir des traductions multilingues (ex. : glossary, market) via un modèle "pull" (appels Python directs). Les interactions HTTP ne sont pas nécessaires actuellement, mais une migration vers HTTP est prévue pour gérer une complexité accrue (ex. : microservices, dashboards internes). FastAPI sera considéré pour les services à haute fréquence (ex. : language, LLM_ai, matching) dans les évolutions futures (V1.1+).
+Multi-tenancy Global : Le multi-tenancy est appliqué globalement aux apps gérant des données par tenant (ex. : company, activation, glossary, market, dico). Utiliser un champ tenant_id (validé par regex ^tenant_[a-zA-Z0-9_]+$) dans les modèles concernés pour isolation et sharding (ex. : partition PostgreSQL par tenant). Les transverses comme language valident cela dans jobs/modèles ; étendre aux verticales via mixins abstraits dans utils_core.
+
 Approche Actuelle : Appels Python Directs
 
 Modèle Pull : Les apps verticales (ex. : glossary, market) appellent directement les services transverses (ex. : language.services.batch_translate_items) via des clients encapsulés (ex. : language_client.py).
@@ -300,6 +304,7 @@
 
 App verticale
 Dépendances transverses
+Multi-tenancy
 
 glossary
 language, seo, LLM_ai, media, taxonomy, matching
@@ -307,6 +312,7 @@
 
 company
 language, seo, media, LLM_ai
+✅ (tenant_id sur profils)
 
 dico
 LLM_ai, taxonomy
@@ -314,6 +320,7 @@
 
 market
 language, matching, taxonomy, metrics
+✅ (tenant_id sur offres)
 
 matching
 LLM_ai, taxonomy
@@ -321,6 +328,7 @@
 
 curation
 language, seo, media, taxonomy, matching, LLM_ai
+✅ (tenant_id sur validations)
 
 logs
 metrics, permissions
@@ -328,6 +336,7 @@
 
 activation
 permissions, metrics
+✅ (tenant_id sur activations)
 
 api
 language, seo, matching, taxonomy

Migration Future : Interactions HTTP

Quand migrer :
Complexité accrue : Déploiement de language comme service indépendant (ex. : conteneur séparé).
Dashboards internes : Affichage des traductions ou stats des jobs via HTTP (ex. : /api/v1/language/translations/).
Microservices : Découplage des apps avec des endpoints HTTP.


Mise en œuvre :
Clients avec switch dynamique : Chaque client (ex. : language_client.py) supporte un mode Python et HTTP via une variable d’environnement (USE_LANGUAGE_HTTP).
Exemple : USE_LANGUAGE_HTTP=true bascule vers requests.post("http://language:8000/api/v1/language/jobs/").


Fallback intelligent : Si HTTP échoue, basculer sur l’appel Python direct pour robustesse.
Endpoints : Activer les endpoints REST dans urls.py, views.py, serializers.py (actuellement commentés avec LANG_ENABLE_API = False).
Versioning : Utiliser /api/v1/language/ pour anticiper les évolutions.
Sécurité : IsAdminUser pour les endpoints sensibles (ex. : /jobs/<pk>/run/), throttling léger (ex. : 200/minute).


Avantages :
Découplage : Apps indépendantes, scalabilité horizontale.
Monitoring : Endpoints pour Grafana (metrics app).
Flexibilité : Prépare l’intégration avec des front-ends (ex. : React).



Préparation pour FastAPI

Cas d’usage :
language : Si déployé comme microservice (ex. : traductions à haute fréquence).
LLM_ai : Appels asynchrones à Mistral API.
matching : Recherches vectorielles rapides (FAISS/pgvector).


Mise en œuvre :
FastAPI pour services futurs : Utiliser FastAPI pour les apps à forte I/O ou calculs vectoriels (ex. : matching, LLM_ai), avec Pydantic pour le typage.
Intégration avec Django : Partager PostgreSQL/pgvector pour l’ORM, utiliser des clients HTTP dans language_client.py pour appeler FastAPI.
Scalabilité : FastAPI avec workers UVicorn/Gunicorn, Redis pour caching, Celery pour async.


Préparation actuelle :
Commenter urls.py, views.py, serializers.py avec LANG_ENABLE_API = False.
Créer des clients (ex. : language_client.py) avec switch Python/HTTP.
Documenter les endpoints potentiels dans urls.py pour une réactivation facile.



Stack Technique

Actuelle :
Django + PostgreSQL/pgvector : ORM, admin, HNSW avec vector_cosine_ops pour recherche sémantique.
Celery + Redis : Tâches asynchrones, caching.
Mistral API : Traductions externes (HTTP).


Future :
FastAPI : Pour services à haute fréquence (ex. : language, LLM_ai, matching).
OpenAPI : Documentation des endpoints HTTP.
Kubernetes : Déploiement distribué des microservices.



Conventions de Développement

Appels Python :
Utiliser des clients encapsulés (ex. : glossary/services/language_client.py).
Mocker les clients dans les tests (ex. : test_language_client.py).


Migration HTTP :
Activer LANG_ENABLE_API = True pour réactiver les endpoints REST.
Ajouter USE_LANGUAGE_HTTP pour basculer vers HTTP.
Tester les endpoints avec pytest-drf.


FastAPI :
Prévoir des services FastAPI pour language, LLM_ai, matching dans V1.1+.
Utiliser Pydantic pour valider les payloads HTTP.
Intégrer avec Django via clients HTTP et PostgreSQL partagé.




📜 Fichier requirements.txt
django==5.2.5
djangorestframework
django-environ
dj-database-url
python-decouple
psycopg2-binary
gunicorn
celery
redis
django-celery-beat
sentence-transformers
faiss-cpu
pgvector

🔌 Intégrations Externes

Mistral API : Enrichissement définitions, résumés.
Societe.com API : Données entreprise (SIREN, raison sociale).

🚀 Démarrage Rapide
docker-compose up --build
http://localhost

🧪 Tests et Qualité
Chaque app respecte PEP8/conventions pour lisibilité/maintenabilité. Tests couvrent hybrid matching et cycle apprentissage.



Outil
Rôle



flake8
Erreurs style


ruff
Linter rapide


black
Formatage PEP8


pytest
Tests unitaires


factory_boy
Objets test


pytest-cov
Couverture


pytest  
pytest --cov=apps  
flake8 apps/

📘 Documentation des Apps
Chaque app a README.md dans apps/README/ (ex. : README_glossary.md). Décrit : objectif métier, modèles, vues/API, tâches Celery, intégrations.
🧱 Squelette apps/app_exemple
apps/
└── transversales|verticales/
    ├── <app_name>/
    │   ├── __init__.py
    │   ├── apps.py              # [0] Config Django
    │   ├── models.py            # [1] Modèles
    │   ├── admin.py             # [6] Admin
    │   ├── forms.py             # [7] Formulaires
    │   ├── serializers.py       # [2] Sérialisation
    │   ├── views.py             # [2] Contrôleurs
    │   ├── services.py          # [3] Logique métier
    │   ├── urls.py              # [5] Routage
    │   ├── tasks.py             # [8] Tâches Celery
    │   ├── utils.py             # [3] Helpers
    │   ├── signals.py           # [9] Événements
    │   ├── permissions.py       # [10] Accès
    │   ├── management/commands/ # [11] CLI
    │   ├── templates/admin/     # [12] Templates admin
    │   ├── static/              # [13-14] JS/CSS
    │   ├── specific/fixtures/   # [15] Fixtures
    └── tests/                   # Tests avec pytest

🧭 Ordre Création + Frontières



Ordre
Fichier
Rôle
Frontière



[0]
apps.py
Déclare app
Pas logique métier


[1]
models.py
Structure données
Pas encoding/enrichissement


[2]
services.py
Logique métier
Pas HTTP/serializers


[3]
serializers.py
Formatage
Pas logique complexe


[4]
views.py
Contrôleurs
Délègue à services.py


[5]
urls.py
Routage
Pas logique


[6]
admin.py
Admin
Pas complexe


[7]
forms.py
Validation
Pas services externes


[8]
tasks.py
Tâches Celery
Délègue à services.py


[9]
signals.py
Événements
Délègue à services.py


[10]
permissions.py
Accès
Pas traitement données


[11]
management/commands/
CLI
Délègue à services.py


[12]
templates/admin/
Templates
Pas Python


[13]
static/*.js
JS
Pas backend


[14]
static/*.css
CSS
Pas backend


[15]
fixtures/
Données test
Pas logique


🧠 Frontières Critiques



Fichier
Appelle services.py
Logique métier
Gère HTTP



views.py
✅
⚠️ Légère
✅


tasks.py
✅
❌ Délègue
❌


signals.py
✅
❌ Délègue
❌


commands/
✅
❌ Délègue
❌


services.py
❌
✅ Cœur
❌


🔗 Dépendances entre Apps
Verticales consomment transverses via pull. Transverses ne dépendent pas des verticales.



App verticale
Dépendances transverses



glossary
language, seo, LLM_ai, media, taxonomy, matching


company
language, seo, media, LLM_ai


dico
LLM_ai, taxonomy


market
language, matching, taxonomy, metrics


matching
LLM_ai, taxonomy


curation
language, seo, media, taxonomy, matching, LLM_ai


logs
metrics, permissions


activation
permissions, metrics


api
language, seo, matching, taxonomy


Interdites : Transverses ne dépendent pas de verticales ; pas de logique métier spécifique ; pas de modification directe.
📜 Règle d’Architecture
🔹 DéfinitionTransverse fournit services techniques/sémantiques (ex. : traduction, SEO, IA). Pas de logique métier propre ; expose interfaces génériques.  
🔹 Principe MaîtriseVerticales contrôlent contexte/déclenchement (pull) ; transverses fournissent résultats sans initiative.  
🔹 ConséquencesPas de modification directe ; pas de décision timing/contexte ; ignore règles métier spécifiques.  
🔹 Exemple : SEO & Glossaryglossary appelle seo avec titre/définition ; seo retourne balises ; glossary décide usage.  
🔹 Schéma[Glossary] ──▶ appelle ──▶ [SEO]↑ Maîtrise métier ↓ Service transverse  
📛 Conventions Nomage



Élément
Convention



App transverse
snake_case, technique (language, seo)


App verticale
snake_case, métier (glossary, dico)


Modèle principal
PascalCase, singulier (GlossaryNode)


Fichier métier
services.py (logique), utils.py (helpers)


Champ traduisible
labels, definition (JSONField)


Tâche Celery
run_generate_X, sync_embeddings_X


Commande CLI
enrich_X.py, sync_faiss_index.py


🚀 Priorités Développement



Phase
Objectifs



1
Transverses : language, seo, LLM_ai, taxonomy, media


2
Verticales base : glossary, company, dico, market, curation


3
Matching/recherche : matching


4
Gouvernance : permissions, logs, activation


5
Exposition : api


App transverse | Prioritélanguage : 🔥 HauteLLM_ai : 🔥 Hautetaxonomy : ⚡ Moyennemedia : ⚡ Moyenneseo : 🌱 Bassemetrics : 🌱 Bassepermissions : 🌱 Basseutils_core : 🌱 Basse



# 0) Baseline du repo (Jour 0)

* Squelette Django + Docker (`config/`, `manage.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`), `nginx.conf`, endpoint `/health`. **DoD**: `docker-compose up --build` → `/health` = 200.

(NB : fait )

# 1) Cadre & conventions (Jour 0)

* Arbo **apps/transversales/** et **apps/verticales/** + `apps/README/README_<apps_XYZ>`.
* Par app : `apps.py`, `models.py`, `services.py`, `serializers.py`, `views.py`, `tasks.py`, `signals.py`, `urls.py`, `tests/`.
* **Frontières** : logique métier dans `services.py` (pas dans `views.py`/`tasks.py`).

(NB : fait )

# 2) Transversales prioritaires (Sprint 1 – J1→J3)

* **language** : `Language`, `TranslatableKey`, `Translation`, `TranslationJob` + `utils.get_active_langs()` et `services.translate_fields(...)`. **DoD**: CRUD admin + tests managers/cache.
* **LLM\_ai** : façade unique (timeouts/retry) pour traductions/résumés (mock en dev). **DoD**: tests d’interface.
* **taxonomy / utils\_core** : JSONFields + helpers génériques. **DoD**: importables sans dépendances circulaires.

( App existante, mais à valider selon nouvelle architecture et nouveau README Brif Technique)


# 3) Verticales de base (Sprint 1 – J3→J5)

* **glossary** : `GlossaryNode(node_id, type, parent, path, labels, description, explication_technique, status/version)`, admin optimisée (search, index, actions), appel `translate_fields` avant `save`. **DoD**: création/validation d’un nœud, path auto.
( App partiellement existante, mais à valider selon nouvelle architecture et nouveau README Brif Technique)
* **company** : `CompanyProfile(company_id, facettes JSON, source, flags)` (collecte brute). **DoD**: POST via DRF.
* **dico** : `Concept(concept_ID, labels, definition, synonyms, related_to, embedding NULL, glossary_node_ids)`, **offline only** (commandes/tasks). **DoD**: CLI `propose_concept_from_glossary` (draft).

# 4) Activation (Sprint 1 – J5)

* **activation** : `CompanyConceptActivation(company_id, concept_ID, facettes, evidence, is_claimed)`, **build offline** depuis `company` + `dico`. **DoD**: commande `activation.build_from_profiles` qui peuple l’index.

# 5) **Matching + Vectorisation (fusion 6 & 7)** (Sprint 2 – J1→J4)

> Une seule app **matching** qui embarque la vectorisation (FAISS/pgvector) **en modules internes** ou **via une mini-façade interne** (aligné V02).

### Modèles / stockage

* **Embeddings** stockés en **pgvector** (PostgreSQL).
* **Index FAISS** persistant dans `faiss_index/` (IVF/HNSW selon tes choix).

### services.py (matching)

* `encode_text(text)`: s’appuie sur sentence-transformers (façade interne).
* `search_lexical(query, corpus=dico.labels+synonyms)`: normalisation + fuzzy.
* `search_vector(query)`: encode→interroge **FAISS** (cosine/sim) en lisant les embeddings (pgvector) pré-indexés.
* `fuse_and_score(lex, vec)`: union pondérée (ex. 0.6/0.4), seuils adaptatifs.
* `filter_by_activation(shortlist, company_activation)`: filtre final runtime.
* `sync_faiss_index()`: **commande** et **task Celery** pour (ré)générer `.index` depuis pgvector.
  **DoD**:
* `sync_faiss_index` produit un `.index` exploitable dans `faiss_index/`.
* `search_vector()` interroge bien l’index (perfs OK en dev).
* `/api/match` (DRF) renvoie une shortlist cohérente **fusion lexical+vectoriel**, **filtrée** par activations.

### views.py (matching)

* `POST /api/match` → payload `{query, filters?}` → retourne `{shortlist: [...], explain: {scores, sources}}`. **Logs** arrivent au step suivant.

# 6) Logs & explicabilité (Sprint 2 – J4)

* **logs** : `QueryMatchLog(request_ID UUID, raw_text, matched_concepts, scores, rationale)` ; hook appelé par `matching.services` post-fusion. **DoD**: chaque `/api/match` crée un log consultable.

# 7) Tâches offline & cron (Sprint 2 – J5)

* Celery Beat :

  * Glossaire **mensuel** (signalement fusions),
  * Dico **bimensuel** (revalidation),
  * Company **hebdo** (rescan modifs).
    **DoD**: tâches « no-op » qui s’exécutent et journalisent correctement.

# 8) Sécurité & API (Sprint 3 – J1)

* Auth token/clé, rate limiting (Nginx/django-ratelimit), CORS si front séparé. **DoD**: `/api/match` protégé (401 si non autorisé).

# 9) CI / Qualité / Tests (Sprint 3 – J1→J2)

* GitHub Actions : ruff/flake8, black, pytest + couverture.
* **Tests critiques** : `matching.services` (fusion/filtre), `language` (cache/validators), `sync_faiss_index`. **DoD**: pipeline vert, >80% sur `matching.services`.

# 10) Monitoring & VPS (Sprint 3 – J2→J3)

* `/health`, Uptime Kuma ou Prometheus/Grafana; VPS Docker Compose (web, db, FAISS, Redis opt., Nginx, Certbot), backups `pg_dump` + `faiss_index/*.index`. **DoD**: domaine + HTTPS opérationnels, backup vérifié.

---

## Backlog immédiat (ordre conseillé)

1. `language` (modèles + services + tests).
2. `glossary` (modèle/admin + path).
3. `company` (API POST).
4. `dico` (Concept draft + CLI).
5. `activation` (build offline).
6. **matching (fusion)** : lexical→vectoriel→`sync_faiss_index`→`/api/match`.

## Seed minimal (pour tester vite)

* 10 nœuds Glossaire, 20 Concepts (labels/synonyms/definition), 5 CompanyProfiles, 10 Activations. **Objectif**: valider `/api/match` dès la fin de la fusion matching+vectorisation.


# Points d’Amélioration (Mineurs, pour Lever Confusion)

Fusion Matching/Vectorisation : Les extraits séparent encore (J1-3 vs J3-4), mais tu notes "fusion 6 & 7" – c'est cohérent avec V07, mais clarifie en un bloc unique "Sprint 2 J1-4 : Matching (incl. Vectorisation FAISS/pgvector)". Intègre search_vector dès J1 avec stub, puis full FAISS J3. Cela évite confusion sur "façade faiss_pgvector plus tard" (obsolète ; tout interne à matching).
Intégration IA/Multilingue/SEO : Aligné (ex. : language/ LLM_ai en Sprint 1), mais ajoute DoD pour multilingue (ex. : traduction labels dans glossary) et SEO (balises via seo dans market). Pour IA, stub rerank dans fuse_and_score via LLM_ai (V07 chapitre 6).
Efficacité pour Junior Dev : DoD concrets sont bons, mais ajoute "stub" pour vectoriel (ex. : mock FAISS avec liste simple) pour tester lexical seul d’abord. Dans README Brief, exemple code avec generate_concept_id est utile ; étends à search_vector stub.
Scalabilité : Ajoute Redis explicitement dans matching pour cache résultats (DoD : "cache hit >80% sur queries répétées"). Pour multilingue, embeddings sentence-transformers supportent multi-lang out-of-box<argument name="citation_id">2&#x3C;/argument&#x3C;/grok:]. SEO via <code>seo</code> app est indépendant, bien pour scale (pages dynamiques). IA (Mistral) scalable avec timeouts/retry dans <code>LLM_ai</code>.</argument>
Maintenance : CI/Grafana bon ; ajoute auto-backup FAISS index dans Celery task (aligné bonnes pratiques pgvector/FAISS<argument name="citation_id">0&#x3C;/argument&#x3C;/grok:]<argument name="citation_id">6&#x3C;/argument&#x3C;/grok:]).</argument></argument>faiss