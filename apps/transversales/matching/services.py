from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from transversales.utils_core.validators import validate_tenant_id, validate_lang, validate_scope
from transversales.utils_core.utils import compute_checksum
from transversales.metrics.services import record_metric
from apps.transversales.language.utils import normalize_locale
from apps.transversales.LLM_ai.services import enrich_ranking, LLMError
from apps.verticales.matching.models import EmbeddingItem
from apps.verticales.matching.specific.encoder import encode_text, batch_encode_texts, EncoderError
from typing import List, Dict, Optional, Any
import logging
import time
import numpy as np
from collections import defaultdict
from rank_bm25 import BM25Okapi
from faiss import IndexFlatIP, IndexIVFFlat, read_index, write_index
import os

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_DIM = getattr(settings, "EMBEDDING_DIM", 384)
MATCH_TOPK_DEFAULT = getattr(settings, "MATCH_TOPK_DEFAULT", 100)
FUSION_WEIGHTS = getattr(settings, "FUSION_WEIGHTS", {"faiss": 0.4, "pgvector": 0.4, "lexical": 0.2})
LLM_RERANK_ENABLED = getattr(settings, "LLM_RERANK_ENABLED", True)
LLM_RERANK_TIMEOUT_MS = getattr(settings, "LLM_RERANK_TIMEOUT_MS", 500)
INDEX_DIR = getattr(settings, "INDEX_DIR", "/path/to/faiss_index")
MATCH_QUOTA = getattr(settings, "MATCH_QUOTA", 1000)  # req/day/tenant

class MatchingError(Exception):
    """Custom exception for matching errors."""
    pass

def encode_texts(texts: List[str], lang: str, tenant_id: Optional[str] = None) -> List[List[float]]:
    """
    Encode a list of texts into embedding vectors.
    Args:
        texts (List[str]): Texts to encode.
        lang (str): Language code (BCP-47, e.g., 'fr', 'pt-br').
        tenant_id (str, optional): Tenant identifier.
    Returns:
        List[List[float]]: List of embedding vectors.
    Raises:
        ValidationError: If inputs are invalid.
        EncoderError: If encoding fails.
    """
    try:
        lang = normalize_locale(lang)
        validate_lang(lang)
        if tenant_id:
            validate_tenant_id(tenant_id)
        return batch_encode_texts(texts, lang, tenant_id)
    except (ValidationError, EncoderError) as e:
        logger.error(f"Failed to encode texts: {str(e)}")
        raise MatchingError(f"Failed to encode texts: {str(e)}")

def upsert_embeddings(
    items: List[Dict[str, Any]],
    tenant_id: Optional[str] = None,
    async_sync: bool = False
) -> Dict[str, Any]:
    """
    Insert or update embeddings in EmbeddingItem and sync FAISS index.
    Args:
        items (List[Dict]): List of items with keys: text, scope, ref_id, lang, payload.
        tenant_id (str, optional): Tenant identifier.
        async_sync (bool): If True, sync FAISS asynchronously via Celery.
    Returns:
        Dict: Stats {'processed': int, 'errors': List[str]}.
    Raises:
        ValidationError: If inputs are invalid.
    """
    from .tasks import sync_dirty  # Avoid circular import

    stats = {"processed": 0, "errors": []}
    try:
        if tenant_id:
            validate_tenant_id(tenant_id)
        for item in items:
            try:
                validate_scope(item.get("scope", ""))
                validate_lang(item.get("lang", ""))
                text = item.get("text", "")
                if not text or not isinstance(text, str):
                    raise ValidationError(_("Text must be a non-empty string"))
                ref_id = item.get("ref_id", "")
                if not ref_id:
                    raise ValidationError(_("ref_id must be non-empty"))

                # Compute checksum
                checksum = compute_checksum(f"{item['scope']}:{ref_id}:{text}")
                embedding = encode_text(text, item["lang"], tenant_id)
                payload = item.get("payload", {})

                # Upsert in DB
                obj, created = EmbeddingItem.objects.update_or_create(
                    tenant_id=tenant_id,
                    scope=item["scope"],
                    ref_id=ref_id,
                    defaults={
                        "lang": normalize_locale(item["lang"]),
                        "model": EMBEDDING_MODEL,
                        "dim": EMBEDDING_DIM,
                        "checksum": checksum,
                        "vector": embedding,
                        "payload": payload,
                    }
                )
                stats["processed"] += 1
                logger.debug(f"{'Created' if created else 'Updated'} EmbeddingItem {item['scope']}:{ref_id}")

            except (ValidationError, EncoderError) as e:
                error_msg = f"Failed to upsert {item.get('scope', 'unknown')}:{item.get('ref_id', 'unknown')}: {str(e)}"
                stats["errors"].append(error_msg)
                logger.error(error_msg)

        # Trigger FAISS sync
        if stats["processed"] > 0:
            if async_sync:
                sync_dirty.delay(tenant_id)
            else:
                sync_faiss_index(tenant_id)
        record_metric(
            name="matching.upsert_embeddings",
            value=stats["processed"],
            tags={"tenant_id": tenant_id or "none", "errors": len(stats["errors"])}
        )
        return stats
    except Exception as e:
        logger.error(f"Upsert embeddings failed: {str(e)}")
        stats["errors"].append(str(e))
        record_metric(
            name="matching.upsert_embeddings_failed",
            value=1,
            tags={"tenant_id": tenant_id or "none", "error": str(e)}
        )
        return stats

def sync_faiss_index(tenant_id: Optional[str] = None) -> None:
    """
    Synchronize FAISS index with pgvector (EmbeddingItem).
    Args:
        tenant_id (str, optional): Tenant identifier.
    """
    try:
        if tenant_id:
            validate_tenant_id(tenant_id)
        items = EmbeddingItem.objects.filter(tenant_id=tenant_id).values("id", "vector")
        if not items:
            logger.warning(f"No items to sync for tenant {tenant_id or 'none'}")
            return

        # Initialize FAISS index
        index = IndexFlatIP(EMBEDDING_DIM)  # Cosine similarity (inner product)
        vectors = np.array([item["vector"] for item in items], dtype=np.float32)
        ids = np.array([item["id"] for item in items], dtype=np.int64)
        index.add_with_ids(vectors, ids)

        # Save index
        index_path = os.path.join(INDEX_DIR, f"faiss_index_{tenant_id or 'default'}.index")
        os.makedirs(INDEX_DIR, exist_ok=True)
        write_index(index, index_path)
        logger.info(f"FAISS index synced for tenant {tenant_id or 'none'}, {len(items)} items")
        record_metric(
            name="matching.faiss_sync_success",
            value=len(items),
            tags={"tenant_id": tenant_id or "none"}
        )
    except Exception as e:
        logger.error(f"FAISS sync failed for tenant {tenant_id or 'none'}: {str(e)}")
        record_metric(
            name="matching.faiss_sync_failed",
            value=1,
            tags={"tenant_id": tenant_id or "none", "error": str(e)}
        )
        raise MatchingError(f"FAISS sync failed: {str(e)}")

def hybrid_search(
    query: str,
    tenant_id: Optional[str],
    scope: str,
    top_k: int = MATCH_TOPK_DEFAULT,
    filters: Optional[Dict[str, Any]] = None,
    lang: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (vectorial + lexical) with RRF/weighted fusion.
    Args:
        query (str): Query text.
        tenant_id (str, optional): Tenant identifier.
        scope (str): Scope (e.g., 'company', 'glossary').
        top_k (int): Number of results to return.
        filters (Dict, optional): Additional filters (e.g., {'sector': 'aeronautique'}).
        lang (str, optional): Language code (BCP-47).
    Returns:
        List[Dict]: List of results with ref_id, score, components, meta.
    Raises:
        ValidationError: If inputs are invalid.
        MatchingError: If search fails.
    """
    try:
        # Validate inputs
        if not query or not isinstance(query, str):
            raise ValidationError(_("Query must be a non-empty string"))
        validate_scope(scope)
        if tenant_id:
            validate_tenant_id(tenant_id)
        if lang:
            lang = normalize_locale(lang)
            validate_lang(lang)
        top_k = min(top_k, MATCH_TOPK_DEFAULT)

        # Translate query if needed
        if lang and lang != normalize_locale(getattr(settings, "DEFAULT_LANG", "fr")):
            try:
                query = translate_text(query, source_lang=lang, target_lang="fr")
                logger.debug(f"Query translated to fr: {query}")
            except LLMError as e:
                logger.warning(f"Translation failed for query: {str(e)}")

        # Encode query
        start_time = time.time()
        query_vector = encode_text(query, lang or "fr", tenant_id)
        latency_encode_ms = (time.time() - start_time) * 1000

        # FAISS search
        faiss_results = []
        try:
            index_path = os.path.join(INDEX_DIR, f"faiss_index_{tenant_id or 'default'}.index")
            if os.path.exists(index_path):
                index = read_index(index_path)
                distances, ids = index.search(np.array([query_vector], dtype=np.float32), top_k)
                faiss_results = [
                    {"id": int(id), "score": float(distance)}
                    for id, distance in zip(ids[0], distances[0])
                ]
        except Exception as e:
            logger.warning(f"FAISS search failed: {str(e)}")
            faiss_results = []

        # pgvector search
        pgvector_results = []
        try:
            items = EmbeddingItem.objects.filter(
                tenant_id=tenant_id, scope=scope
            ).order_by(VectorField("vector").cosine_distance(query_vector))[:top_k]
            pgvector_results = [
                {"id": item.id, "score": 1 - item.vector.cosine_distance(query_vector)}
                for item in items
            ]
        except Exception as e:
            logger.warning(f"pgvector search failed: {str(e)}")

        # Lexical search (BM25)
        lexical_results = []
        try:
            corpus = [item.payload.get("text", "") for item in EmbeddingItem.objects.filter(tenant_id=tenant_id, scope=scope)]
            if corpus:
                bm25 = BM25Okapi([text.split() for text in corpus])
                scores = bm25.get_scores(query.split())
                lexical_results = [
                    {"id": item.id, "score": float(score)}
                    for item, score in zip(EmbeddingItem.objects.filter(tenant_id=tenant_id, scope=scope), scores)
                    if score > 0
                ]
                lexical_results = sorted(lexical_results, key=lambda x: x["score"], reverse=True)[:top_k]
        except Exception as e:
            logger.warning(f"Lexical search failed: {str(e)}")

        # Fuse results (RRF)
        scores = defaultdict(float)
        components = defaultdict(lambda: {"faiss": 0.0, "pgvector": 0.0, "lexical": 0.0})
        for rank, result in enumerate(faiss_results, 1):
            scores[result["id"]] += FUSION_WEIGHTS["faiss"] / (rank + 60)
            components[result["id"]]["faiss"] = result["score"]
        for rank, result in enumerate(pgvector_results, 1):
            scores[result["id"]] += FUSION_WEIGHTS["pgvector"] / (rank + 60)
            components[result["id"]]["pgvector"] = result["score"]
        for rank, result in enumerate(lexical_results, 1):
            scores[result["id"]] += FUSION_WEIGHTS["lexical"] / (rank + 60)
            components[result["id"]]["lexical"] = result["score"]

        # Apply filters
        filtered_ids = set(scores.keys())
        if filters:
            q = Q()
            for key, value in filters.items():
                q &= Q(payload__contains={key: value})
            filtered_ids = set(EmbeddingItem.objects.filter(q, id__in=filtered_ids).values_list("id", flat=True))

        # Rerank with LLM if enabled
        results = [
            {
                "id": id,
                "score": score,
                "components": components[id]
            }
            for id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if id in filtered_ids
        ][:top_k]
        if LLM_RERANK_ENABLED:
            try:
                start_time = time.time()
                reranked = enrich_ranking(
                    query=query,
                    items=[{"id": r["id"], "text": EmbeddingItem.objects.get(id=r["id"]).payload.get("text", "")} for r in results],
                    timeout_ms=LLM_RERANK_TIMEOUT_MS
                )
                results = [
                    {
                        "id": item["id"],
                        "score": item["score"],
                        "components": components[item["id"]]
                    }
                    for item in reranked
                ]
                latency_rerank_ms = (time.time() - start_time) * 1000
                record_metric(
                    name="matching.rerank_latency_ms",
                    value=latency_rerank_ms,
                    tags={"tenant_id": tenant_id or "none"}
                )
            except LLMError as e:
                logger.warning(f"LLM reranking failed: {str(e)}")
                record_metric(
                    name="matching.rerank_failed",
                    value=1,
                    tags={"tenant_id": tenant_id or "none", "error": str(e)}
                )

        # Fetch metadata
        final_results = []
        for result in results:
            try:
                item = EmbeddingItem.objects.get(id=result["id"])
                final_results.append({
                    "ref_id": item.ref_id,
                    "score": result["score"],
                    "components": result["components"],
                    "meta": item.payload
                })
            except EmbeddingItem.DoesNotExist:
                continue

        # Record metrics
        latency_total_ms = (time.time() - start_time) * 1000
        record_metric(
            name="matching.hybrid_search_latency_ms",
            value=latency_total_ms,
            tags={"tenant_id": tenant_id or "none", "scope": scope, "top_k": top_k}
        )
        record_metric(
            name="matching.hybrid_search_success",
            value=len(final_results),
            tags={"tenant_id": tenant_id or "none", "scope": scope}
        )

        return final_results

    except Exception as e:
        logger.error(f"Hybrid search failed: {str(e)}")
        record_metric(
            name="matching.hybrid_search_failed",
            value=1,
            tags={"tenant_id": tenant_id or "none", "scope": scope, "error": str(e)}
        )
        raise MatchingError(f"Hybrid search failed: {str(e)}")

def generate_shortlist(
    query: str,
    tenant_id: Optional[str],
    scope: str,
    top_k: int = MATCH_TOPK_DEFAULT,
    filters: Optional[Dict[str, Any]] = None,
    lang: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a shortlist of matching items.
    Args:
        query (str): Query text.
        tenant_id (str, optional): Tenant identifier.
        scope (str): Scope (e.g., 'company', 'glossary').
        top_k (int): Number of results to return.
        filters (Dict, optional): Additional filters.
        lang (str, optional): Language code (BCP-47).
    Returns:
        Dict: Results and explanations {'results': List[Dict], 'explanations': Dict}.
    """
    try:
        results = hybrid_search(query, tenant_id, scope, top_k, filters, lang)
        explanations = {
            "matched_terms": query.split(),  # Simple tokenization for now
            "components": {
                "faiss": FUSION_WEIGHTS["faiss"],
                "pgvector": FUSION_WEIGHTS["pgvector"],
                "lexical": FUSION_WEIGHTS["lexical"]
            }
        }
        return {"results": results, "explanations": explanations}
    except MatchingError as e:
        logger.error(f"Generate shortlist failed: {str(e)}")
        return {"results": [], "explanations": {"error": str(e)}}