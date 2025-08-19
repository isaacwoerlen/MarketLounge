📘 README — App faiss_pgvector

Ce fichier respecte les conventions décrites dans [README Brief Technique.md](../README Brief Technique.md), situé à la racine du dossier apps/.Il décrit l’objectif, le type, les composants, l’intégration, et les responsabilités internes de l’app.


🧩 Type d’app



Type
Description



Transversale
Fournit un moteur de vectorisation et de recherche sémantique



Cette app est transversale, utilisée par toutes les apps verticales (ex: language, glossary, champs SEO/OG) pour encoder des textes en vecteurs et effectuer des recherches sémantiques rapides. Elle n’appelle jamais les apps métier (découplage strict).


🎯 Objectif
L’app faiss_pgvector est conçue pour :

Encoder des textes en vecteurs via sentence-transformers.
Stocker les vecteurs dans PostgreSQL via l’extension pgvector.
Indexer les vecteurs localement avec FAISS pour des recherches rapides.
Fournir une API interne stable (services.py) pour les apps métier (si besoin)
Supporter le multi-tenancy via tenant_id et les recherches par scope.
Permettre des recherches hybrides (pgvector + FAISS) pour précision et vitesse.
Monitorer les performances des index FAISS (taille, latence).


🤔 Pourquoi pgvector ? Pourquoi FAISS ?
🔹 pgvector

Stockage persistant des vecteurs dans PostgreSQL.
Requêtes SQL vectorielles avec opérateurs (<->, cosine).
Index vectoriel (ivfflat) pour top-k rapide.
Compatible avec filtres SQL (scope, tenant_id, langue).
Idéal pour volumes modérés ou requêtes hybrides.

🔹 FAISS

Indexation en mémoire pour recherches ultra-rapides.
Optimisé pour volumes massifs (>100k vecteurs).
Top-k en temps quasi réel.
Moins flexible pour filtres complexes.
Nécessite gestion des fichiers .index et synchronisations.


🧠 pgvector vs FAISS : qui fait quoi ?



Fonction
pgvector
FAISS



Stockage persistant
✅ Oui
❌ Non (fichiers .index)


Requêtes SQL hybrides
✅ Oui
❌ Non


Recherche top-k rapide
⚠️ Moyenne
✅ Excellente


Scalabilité (millions de vecteurs)
⚠️ Limite serveur SQL
✅ Très bonne


Facilité de déploiement
✅ Intégré PostgreSQL
⚠️ Nécessite gestion des index


Auditabilité / debug
✅ Très lisible
❌ Peu lisible



🔮 Évolution possible des rôles



Phase du projet
Rôle de pgvector
Rôle de FAISS



MVP
Stockage principal + recherches
Indexation secondaire pour top-k


Scale-up
Stockage persistant + hybrid
Recherche primaire + sharding


Mature
Backup + audits
Recherche optimisée + clustering



🧱 Modèle(s) principal(aux)
Pas de modèles propres, mais un mixin abstrait pour les apps métier, défini dans models.py :
from pgvector.django import VectorField
from django.conf import settings
from django.db import models

class EmbeddingMixin(models.Model):
    embedding = VectorField(dim=settings.EMBEDDING_DIM, null=True, blank=True)

    class Meta:
        abstract = True

Exemple dans language :
from transversales.faiss_pgvector.models import EmbeddingMixin

class Translation(EmbeddingMixin):
    key = models.ForeignKey(TranslatableKey, on_delete=models.CASCADE)
    language = models.CharField(max_length=10)
    text = models.TextField()
    # embedding hérité de EmbeddingMixin

Exemple dans glossary :
from transversales.faiss_pgvector.models import EmbeddingMixin

class GlossaryNode(EmbeddingMixin):
    definition = models.TextField()
    # embedding hérité de EmbeddingMixin


🧠 Logique métier

Encodage : encode_text(text: str) -> np.ndarray utilise sentence-transformers pour générer un vecteur normalisé L2 (dim=EMBEDDING_DIM, float32).
Stockage : store_vector(obj, vector: np.ndarray) met à jour le champ embedding via pgvector.
Recherche : search_similar(vector: np.ndarray, scope: str, top_k: int = 10, tenant_id: str | None = None) -> List[Result] utilise FAISS (IndexFlatIP, ou pgvector si FAISS_ENABLED=False) avec filtre par tenant_id et scope.
Synchronisation : Tâche Celery sync_embeddings aligne pgvector et FAISS.
Monitoring : Tâche monitor_index collecte stats (taille index, temps de recherche).

Flux avec language :

Traduction batch :
language.services.batch_translate_scope appelle LLM_ai.services.translate_text.
Traduction stockée via store_translation.
Vectorisation via encode_text/store_vector (async si LANG_EMBED_SYNC=False).
language.tasks.run_vectorize_scopes appelle faiss_pgvector.services.upsert.


Recherche sémantique :
language.services appelle encode_text et search_similar pour suggestions de traductions.
Règles de réutilisation (score minimum, placeholders) gérées dans language.


Rebuild FAISS :
language pousse Translation.embedding via faiss_pgvector.services.build.




🔍 Règles de recherche

Normalisation : Les embeddings sont normalisés (L2) dans encode_text pour cohérence.
Métrique : Utilise vector_cosine_ops pour pgvector et IndexFlatIP pour FAISS (cosine similarity, vecteurs normalisés).
Cohérence : Les scores entre pgvector et FAISS sont alignés grâce à la normalisation L2.


🔌 Intégrations externes

sentence-transformers : Encodage des textes.
pgvector : Stockage des vecteurs (extension PostgreSQL vector).
FAISS : Indexation rapide (fichiers .index).
LLM_ai : Enrichissement sémantique avant vectorisation (ex: paraphrase via Mistral).
Apps métier : Consomment via transversales.faiss_pgvector.services.

Exemple multi-tenant :
from transversales.faiss_pgvector.services import encode_text, search_similar

vector = encode_text("Hello world")
results = search_similar(vector, scope="translation", tenant_id="tenant1")
# Dans language : vérifier score > 0.9 et placeholders intacts


⏱ Tâches Celery

sync_embeddings : Synchronise pgvector -> FAISS pour un scope/tenant.
recalculate_embeddings : Recalcule embeddings pour un scope donné.
monitor_index : Collecte stats (taille index, temps de recherche).


📂 Structure interne de l’app
transversales/faiss_pgvector/
├── __init__.py
├── apps.py
├── models.py            # EmbeddingMixin pour apps métier
├── services.py          # API publique: encode_text, store_vector, search_similar, upsert, build
├── tasks.py             # sync_embeddings, recalculate_embeddings, monitor_index
├── management/
│   └── commands/
│       └── sync_faiss_index.py
├── specific/
│   ├── embeddings.py
│   ├── pgvector_backend.py
│   ├── faiss_backend.py
│   └── fixtures/
│       └── faiss_index_empty.index
└── tests/
    ├── test_services.py
    ├── test_embeddings.py
    ├── test_pgvector_backend.py
    ├── test_faiss_backend.py
    ├── test_tasks.py
    ├── test_models.py
    └── factories.py


🧭 Règles de structuration

Pas de dépendance aux apps métier (ex: language, glossary).
API publique via services.py (from transversales.faiss_pgvector.services import encode_text).
Fichiers backend dans specific/ (embeddings.py, pgvector_backend.py, faiss_backend.py).
Mixin dans models.py (EmbeddingMixin).
Index FAISS persistés en faiss_index/<tenant>/<scope>.index.
Tâches Celery pour cohérence pgvector/FAISS.


📦 Intégration dans les apps métier
Exemple avec language :
from transversales.faiss_pgvector.services import encode_text, store_vector, search_similar
from transversales.faiss_pgvector.models import EmbeddingMixin

def vectorize_translation(translation):
    vector = encode_text(translation.text)
    store_vector(translation, vector)
    translation.save()  # Persistance par language
    similar = search_similar(vector, scope="translation", tenant_id=translation.key.tenant_id)
    # Vérifier score > 0.9 et placeholders dans language

Exemple avec glossary :
from pgvector.django import VectorField
from django.conf import settings
from transversales.faiss_pgvector.services import encode_text, store_vector
from transversales.faiss_pgvector.models import EmbeddingMixin

class GlossaryNode(EmbeddingMixin):
    definition = models.TextField()
    # embedding hérité de EmbeddingMixin

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        vector = encode_text(self.definition)
        store_vector(self, vector)


🚀 Recommandations pour scalabilité

Indexing : Index ivfflat sur embedding avec vector_cosine_ops.
Sharding : Partitionner par tenant_id et scope (ex: faiss_index/<tenant>/<scope>.index).
Performance : Tester avec 10M+ vecteurs via factory_boy. Limiter RAM FAISS (ex: 16GB par index).
Multi-tenancy : Filtrer par tenant_id dans search_similar.
Batching : Utiliser bulk_update pour pgvector, batch pour FAISS upsert.
Mémoire FAISS : Monitorer RAM via monitor_index et limiter taille index par tenant/scope.


📛 Conventions de nommage

Champs : snake_case (ex: embedding).
Tâches Celery : run_vectorize_scopes, sync_embeddings, monitor_index.
Commandes CLI : sync_faiss_index.py.
Scopes : snake_case ou hiérarchique (ex: translation, glossary:node).
Index FAISS : <tenant>/<scope>.index.


🧑‍💻 Changements récents

Ajout façade services.py pour API stable.
Déplacement backends dans specific/ (embeddings.py, pgvector_backend.py, faiss_backend.py).
Support multi-tenant via tenant_id dans search_similar.
Setting EMBEDDING_DIM pour cohérence.
Standardisation sur .index pour FAISS (remplace .npy du Brief Technique, à mettre à jour).
Tâche monitor_index pour performances.
Normalisation L2 pour cohérence cosine.
Ajout de models.py pour héberger EmbeddingMixin, centralisant la logique de VectorField.


🧪 Tests

Localisation : transversales/faiss_pgvector/tests/.
Framework : pytest, factory_boy, pytest-cov.
Cas testés :
encode_text : Dimension correcte (EMBEDDING_DIM), dtype float32, normalisation L2.
store_vector : Stockage dans pgvector.
search_similar : Résultats top-k, filtrage par tenant_id/scope.
sync_embeddings : Cohérence pgvector/FAISS.
monitor_index : Stats (taille, latence).
EmbeddingMixin : Champ embedding avec VectorField(dim=EMBEDDING_DIM).




📂 Fixtures

specific/fixtures/faiss_index_empty.index : Index FAISS vide pour initialisation.
Chargement via commande sync_faiss_index.py pour créer des index par tenant_id/scope.


🧪 Conclusion
L’app faiss_pgvector est robuste, scalable, et prête pour l’IA sémantique. Elle respecte les frontières de README Brief Technique.md, centralise la vectorisation/recherche, et s’intègre avec language, glossary, et champs SEO/OG. Les tests et le multi-tenancy sont prioritaires pour gros volumes.