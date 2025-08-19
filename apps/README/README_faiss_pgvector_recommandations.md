📋 Recommandations pour le développeur — App faiss_pgvector
Ce document fournit des recommandations pour développer et maintenir l’app faiss_pgvector, une app transversale pour la vectorisation et la recherche sémantique, utilisée par toutes les apps verticales (ex: language, glossary, champs SEO/OG). Suivez ces pratiques pour garantir un code robuste, scalable, et prêt pour l’IA sémantique, tout en respectant les conventions de README Brief Technique.md.
🛠 Ordre de développement recommandé

Configurer les bases :
Implémenter apps.py (FaissPgvectorConfig pour signaux) et settings.py (EMBEDDING_DIM, FAISS_ENABLED, etc.).
Tester : tests/test_settings.py (valider EMBEDDING_DIM > 0, FAISS_ENABLED or PGVECTOR_ENABLED).


Définir la façade :
Créer services.py avec API publique (encode_text, store_vector, search_similar, upsert, build) sous forme de stubs.
Tester : tests/test_services.py (valider signatures, exceptions).


Backend pgvector :
Implémenter specific/pgvector_backend.py (store_vector, fetch_vectors).
Tester : tests/test_pgvector_backend.py (stockage/lecture, dimension).


Backend FAISS :
Implémenter specific/faiss_backend.py (build_index, search_similar, upsert).
Tester : tests/test_faiss_backend.py (top-k, idempotence).


Connecter la façade :
Compléter services.py pour router vers pgvector_backend et faiss_backend.
Tester : tests/test_services.py (intégration complète).


Tâches Celery :
Implémenter tasks.py (sync_embeddings, recalculate_embeddings, monitor_index).
Tester : tests/test_tasks.py (cohérence pgvector/FAISS, stats).


Commandes CLI :
Implémenter management/commands/sync_faiss_index.py (appelle sync_embeddings) et rebuild_collection.py (reconstruit index spécifique).
Tester : Valider via CLI.



🔑 Bonnes pratiques

Découplage strict :
faiss_pgvector ne doit jamais importer language, glossary, ou LLM_ai.
Apps métier appellent transversales.faiss_pgvector.services (ex: encode_text, search_similar).
Pourquoi : Évite les cycles, permet de remplacer FAISS par Milvus/Weaviate sans toucher les apps métier.


Normalisation & métrique :
Normaliser tous les vecteurs (L2) dans encode_text pour cohérence cosine.
Utiliser vector_cosine_ops (pgvector) et IndexFlatIP (FAISS, vecteurs normalisés).
Vérifier dans services.py : vector.shape == (settings.EMBEDDING_DIM,) et dtype float32.
Pourquoi : Garantit des scores cohérents entre pgvector et FAISS.


Idempotence :
store_vector : Mettre à jour obj.embedding sans .save().
upsert : Supporter ré-exécutions (ex: mise à jour si ID existe).
build : Écrire atomiquement (.index.tmp → rename).
Pourquoi : Évite les erreurs en batch ou retry.


Multi-tenant et scope :
Utiliser collection = f"{tenant_id or 'default'}:{scope}" dans search_similar, upsert, build.
Stocker index FAISS dans faiss_index//.index.
Pourquoi : Évite collisions, supporte sharding.


Aucune persistance directe :
faiss_pgvector remplit obj.embedding mais ne fait jamais .save().
Apps métier (language, glossary) gèrent la persistance.
Pourquoi : Respecte les frontières des apps métier.


Utilisation du mixin :
Apps métier doivent hériter de EmbeddingMixin (dans transversales.faiss_pgvector.models) pour définir le champ embedding.


Configuration centralisée :
Utiliser settings.py pour EMBEDDING_DIM, EMBEDDING_MODEL, FAISS_ENABLED, PGVECTOR_ENABLED, FAISS_INDEX_DIR, LANG_EMBED_SYNC.
Valider via asserts (ex: assert EMBEDDING_DIM > 0).
Pourquoi : Évite incohérences (ex: dimension mismatch).


Tests prioritaires :
Tester chaque composant dès son développement :
encode_text : shape == (EMBEDDING_DIM,), dtype == float32, L2 ≈ 1 (cosine).
store_vector : Stockage pgvector, lève erreur si dimension incorrecte.
search_similar : Top-1 renvoie ID correct, filtrage tenant_id/scope.
upsert : Idempotent (ré-exécution sans crash).
build : Index cohérent avec pgvector.


Utiliser pytest, factory_boy, pytest-cov (voir tests/).



⚠️ Pièges à éviter

Imports croisés :
Ne jamais importer language ou LLM_ai dans faiss_pgvector.
Solution : Utiliser services.py comme façade publique.


Incohérence dimension :
Ne pas coder en dur 384 ; utiliser settings.EMBEDDING_DIM.
Solution : Valider dimensions dans encode_text, store_vector, upsert, build.


Persistance non atomique :
Ne pas écrire directement .index ; utiliser .index.tmp → rename.
Solution : Implémenter atomicité dans faiss_backend.build_index.


Manque de tests :
Ne pas développer sans tests unitaires pour chaque composant.
Solution : Suivre les tests rapides proposés (encode, store, search).


Couplage avec DB métier :
Ne pas appeler .save() dans faiss_pgvector.
Solution : Laisser language/glossary gérer la DB.



🚀 Exemple d’intégration
Dans language :
from transversales.faiss_pgvector.services import encode_text, store_vector, search_similar
from transversales.faiss_pgvector.models import EmbeddingMixin

def vectorize_translation(translation):
    vector = encode_text(translation.text)
    store_vector(translation, vector)
    translation.save()  # Persistance par language
    similar = search_similar(vector, scope="translation", tenant_id=translation.key.tenant_id)
    if similar and similar[0][1] > 0.9:  # Seuil dans language
        # Réutiliser traduction

Dans tasks.py (batch) :
from celery import shared_task
from django.conf import settings
from transversales.faiss_pgvector.services import upsert, build

@shared_task
def run_vectorize_scopes(scope, tenant_id):
    translations = Translation.objects.filter(key__scope=scope, key__tenant_id=tenant_id)
    vectors = [encode_text(t.text) for t in translations]
    ids = [str(t.id) for t in translations]
    collection = f"{tenant_id}:{scope}"
    upsert(collection, ids, vectors)
    build(collection, [(id, vec) for id, vec in zip(ids, vectors)])

🧪 Tests recommandés

Encodage :
def test_encode_text():
    vector = encode_text("test")
    assert vector.shape == (settings.EMBEDDING_DIM,)
    assert vector.dtype == np.float32
    assert abs(np.linalg.norm(vector) - 1.0) < 1e-6  # Normalisé L2


Stockage :
@pytest.mark.django_db
def test_store_vector():
    translation = TranslationFactory()
    vector = encode_text(translation.text)
    store_vector(translation, vector)
    assert translation.embedding is not None
    assert len(translation.embedding) == settings.EMBEDDING_DIM


Recherche :
@pytest.mark.django_db
def test_search_similar():
    translation = TranslationFactory()
    vector = encode_text(translation.text)
    store_vector(translation, vector)
    results = search_similar(vector, scope="translation", tenant_id=translation.key.tenant_id)
    assert results[0][0] == str(translation.id)  # Top-1 correct



📌 Conclusion
Suivez cet ordre et ces pratiques pour développer faiss_pgvector de manière robuste, scalable, et découplée. Priorisez les tests à chaque étape et respectez les frontières entre apps transversales et verticales. L’app est prête pour l’IA sémantique (matching, enrichissement) et le multi-tenancy (sharding, scope).