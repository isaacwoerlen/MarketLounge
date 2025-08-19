README_matching
Objectif
L’app matching est transversale, centralisant la recherche sémantique et le matching entre requêtes acheteurs (ex. : "soudure inox 316L, aéronautique, nord") et company profiles/concepts, générant des shortlists. Elle intègre l’encodage (sentence-transformers), stockage/indexation (pgvector/FAISS), recherche hybride (vectoriel + BM25), reranking, et monitoring. Elle supporte le multi-tenancy via tenant_id et recherches par scope.
Fonctionnement

Encodage : Encode textes en vecteurs multilingues (sentence-transformers/paraphrase-multilingual).
Stockage : PostgreSQL via pgvector (vérité unique, index HNSW).
Indexation : FAISS local pour vitesse (artefact dérivé, versioning, dirty_ratio).
Recherche hybride : Vectoriel (FAISS/pgvector) + lexique (BM25/trigrammes), fusion scores via RRF ou pondération (weights: faiss=0.4, pgvector=0.4, lexical=0.2; tie-break: pgvector > lexical).
Reranking : Via LLM_ai.services.enrich_ranking (activable via LLM_RERANK_ENABLED, timeout 500ms, fallback à vectoriel+lexical si timeout).
Multi-tenancy : Filtrage obligatoire tenant_id/scope avant fusion.
Multilingue : Embeddings multilingues, normalisation BCP-47 (ex. : pt-br), détection langue optionnelle via langdetect.
Monitoring : Métriques (matching.index_latency, matching.recall_k, matching.faiss_hit_rate, matching.fusion_component_share) via metrics.services, logs (transversales.matching).
Pipeline :graph TD
    A[Query] --> B[Prétraitement: normalize, langdetect]
    B --> C[Encode: encoder.py]
    C --> D[FAISS top-1000]
    C --> E[BM25 top-300]
    D --> F[Filtrage: storage.py]
    E --> F
    F --> G[Rerank: LLM_ai]
    G --> H[Fusion: RRF/pondéré]
    H --> I[ScoredHit: ref_id, score, components]


Health states : Green (dirty_ratio<0.05), Amber (0.05-0.1), Red (>0.1, fallback pgvector+lexical).
Fallback : Si FAISS red, utilise pgvector+lexical; reranking désactivé si timeout ou LLM_RERANK_ENABLED=False.

Cas d’usage

Achat industriel : Match "soudure inox 316L, aéronautique, nord" → shortlist entreprises.
RH : Match CV (ex. : "ingénieur aéronautique") → offres emploi.
Glossaire : Match termes (ex. : "usinage") → concepts dico.

Intégration

Avec language : Traduit queries/labels avant encodage (fallback via LLM_ai).
Avec dico : Match concept_IDs via matcher.hybrid_search.
Avec market : Shortlists via services.generate_shortlist.
Avec LLM_ai : Reranking via enrich_ranking.
Avec api : Exposition publique via api.views.match.
Multi-tenancy : tenant_id/scope dans tous services.

Fichiers

Standards :
models.py : EmbeddingItem (tenant_id, scope, ref_id, lang, model, dim, checksum, vector, payload).
admin.py : Admin pour EmbeddingItem (staff-only, filtrage tenant_id).
services.py : API publique (encode_texts, hybrid_search, generate_shortlist, upsert_embeddings).
tasks.py : Tâches Celery (build_index, sync_dirty, reembed).
views.py : API REST (/api/v1/matching/).
urls.py : Routes API.
apps.py : Configuration, checks.
serializers.py : Sérialisation EmbeddingItem.


Spécifiques :
specific/encoder.py : Encodage texte → vecteurs.
specific/storage.py : Upsert/search pgvector, BM25.
specific/index_faiss.py : Gestion index FAISS (versioning, dirty_ratio).
specific/matcher.py : Logique hybrid search, reranking.


Management commands :
management/commands/rebuild_index.py : Rebuild FAISS.
management/commands/check_health.py : Vérifie dirty_ratio, latence.


Tests :
tests/test_models.py : Validation EmbeddingItem.
tests/test_services.py : Tests API publique.
tests/test_tasks.py : Tests Celery.
tests/test_views.py : Tests API REST.
tests/test_admin.py : Tests admin.
tests/test_encoder.py : Tests encodage.
tests/test_storage.py : Tests pgvector.
tests/test_index_faiss.py : Tests FAISS.
tests/test_matcher.py : Tests hybrid search.
tests/test_integration.py : Tests flux complet.
tests/factories.py : Factories pour EmbeddingItem.



Tests

Couverture : >80% (pytest --cov=transversales.matching).
Unitaires : Validation modèles, services, tâches, API, encodage, indexation.
Intégration : Flux encodage → storage → index → search → shortlist.
Cas couverts :
Isolation tenant_id/scope.
Cohérence pgvector/FAISS (dirty_ratio<0.05).
Recherche hybride (RRF, weights).
Erreurs (timeout, index load failure).


Commandes :pytest tests/ --cov=transversales.matching --cov-report=html



Déploiement

Dépendances : sentence-transformers, faiss-cpu (ou faiss-gpu), celery[redis], django-rest-framework.
Docker Compose :services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    depends_on: [db, redis]
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
  redis:
    image: redis:6
  celery:
    build: .
    command: celery -A config worker -Q matching_queue -l info
    depends_on: [redis]


Settings :
EMBEDDING_MODEL="sentence-transformers/paraphrase-multilingual".
EMBEDDING_DIM=384.
MATCH_TOPK_DEFAULT=100.
FUSION_WEIGHTS={"faiss": 0.4, "pgvector": 0.4, "lexical": 0.2}.
INDEX_DIR="/path/to/faiss_index".
LLM_RERANK_ENABLED=True.
LLM_RERANK_TIMEOUT_MS=500.
MATCH_QUOTA=1000 (req/jour/tenant).


Warmup : Charge FAISS index au démarrage (lazy via cache).
Cron : rebuild_index (quotidien), check_health (horaire).
CI/CD : GitHub Actions (pytest, flake8).

Sécurité

Filtres tenant_id : Obligatoires dans storage.py/matcher.py.
Permissions : Staff-only pour admin, TokenAuthentication pour API.
Quotas : Par tenant (MATCH_QUOTA).
Back-pressure : 429 + Retry-After pour API.
Index FAISS : Backup périodique, dirty_ratio>0.05 déclenche rebuild, rollback vers previous_version si health=red.

Contrats DB

Table EmbeddingItem :
tenant_id: text (regex: tenant_[a-zA-Z0-9_]+).
scope: text (ex. : company, glossary).
ref_id: text (ex. : company_id, concept_id).
lang: text (BCP-47, ex. : fr, pt-br).
model: text (ex. : sentence-transformers/paraphrase-multilingual).
dim: int (ex. : 384).
checksum: sha256 (texte source).
vector: vector(dim) (pgvector).
payload: jsonb (ex. : {"sector": "aeronautique"}).
Contraintes : unique(tenant_id, scope, ref_id).
Indexes : HNSW(vector, m=16, ef_construction=100), tenant_id, scope, lang.



API Exemples

POST /api/v1/matching/match :{
  "query": "soudure inox 316L, aéronautique, nord",
  "tenant_id": "tenant_123",
  "scope": "company",
  "top_k": 10,
  "filters": {"sector": "aeronautique", "region": "nord"}
}

Response :{
  "results": [
    {
      "ref_id": "comp_1",
      "score": 0.95,
      "components": {"faiss": 0.5, "pgvector": 0.3, "lexical": 0.15},
      "meta": {"company_name": "Acme Welding"}
    }
  ],
  "explanations": {"matched_terms": ["soudure"], "components": {"faiss": 0.5, "pgvector": 0.3}}
}


POST /api/v1/matching/upsert :{
  "items": [
    {
      "tenant_id": "tenant_123",
      "scope": "company",
      "ref_id": "comp_1",
      "lang": "fr",
      "text": "Soudure inox 316L",
      "payload": {"sector": "aeronautique"}
    }
  ]
}

Response :{
  "processed": 1,
  "errors": []
}



Notes

Multilingue : Embeddings multilingues, détection via langdetect (optionnelle).
Indexation : pgvector vérité unique, FAISS sync via tasks.sync_dirty.
Monitoring : SLIs (p95<250ms, recall_k>0.9, faiss_hit_rate>0.7).
