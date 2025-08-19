from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from transversales.utils_core.validators import validate_tenant_id, validate_lang
from transversales.metrics.services import record_metric
from apps.transversales.language.utils import normalize_locale
from sentence_transformers import SentenceTransformer
import logging
import numpy as np
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual")
EMBEDDING_DIM = getattr(settings, "EMBEDDING_DIM", 384)
CACHE_TTL = getattr(settings, "MATCHING_CACHE_TTL", 3600)  # 1h cache for embeddings
MODEL = None  # Global model instance (lazy-loaded)

class EncoderError(Exception):
    """Custom exception for encoding errors."""
    pass

def load_model() -> SentenceTransformer:
    """
    Load the sentence-transformers model (lazy initialization).
    Returns:
        SentenceTransformer: Loaded model instance.
    Raises:
        EncoderError: If model loading fails.
    """
    global MODEL
    if MODEL is None:
        try:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            MODEL = SentenceTransformer(EMBEDDING_MODEL)
            record_metric(
                name="matching.model_load_success",
                value=1,
                tags={"model": EMBEDDING_MODEL}
            )
        except Exception as e:
            logger.error(f"Failed to load model {EMBEDDING_MODEL}: {str(e)}")
            record_metric(
                name="matching.model_load_failed",
                value=1,
                tags={"model": EMBEDDING_MODEL, "error": str(e)}
            )
            raise EncoderError(f"Failed to load model: {str(e)}")
    return MODEL

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_if_exception_type(EncoderError),
    reraise=True
)
def encode_text(text: str, lang: str, tenant_id: Optional[str] = None) -> List[float]:
    """
    Encode a single text into an embedding vector.
    - Normalizes language code using language.utils.normalize_locale.
    - Uses cache to avoid re-encoding identical texts.
    - Validates inputs (text, lang, tenant_id).
    Args:
        text (str): Text to encode.
        lang (str): Language code (BCP-47, e.g., 'fr', 'pt-br').
        tenant_id (str, optional): Tenant identifier.
    Returns:
        List[float]: Normalized embedding vector.
    Raises:
        ValidationError: If inputs are invalid.
        EncoderError: If encoding fails.
    """
    try:
        # Validate inputs
        if not text or not isinstance(text, str):
            logger.error("Invalid text: must be a non-empty string")
            raise ValidationError(_("Text must be a non-empty string"))
        lang = normalize_locale(lang)
        validate_lang(lang)
        if tenant_id:
            validate_tenant_id(tenant_id)

        # Cache key
        cache_key = f"matching:embed:{tenant_id or 'none'}:{lang}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        cached_embedding = cache.get(cache_key)
        if cached_embedding is not None:
            logger.debug(f"Cache hit for embedding: {cache_key}")
            record_metric(
                name="matching.encode_cache_hit",
                value=1,
                tags={"tenant_id": tenant_id or "none", "lang": lang}
            )
            return cached_embedding

        # Load model
        model = load_model()

        # Encode text
        start_time = time.time()
        embedding = model.encode([text], normalize_embeddings=True)[0].tolist()
        latency_ms = (time.time() - start_time) * 1000

        # Validate dimension
        if len(embedding) != EMBEDDING_DIM:
            logger.error(f"Invalid embedding dimension: {len(embedding)}, expected {EMBEDDING_DIM}")
            raise EncoderError(f"Invalid embedding dimension: {len(embedding)}")

        # Cache result
        cache.set(cache_key, embedding, timeout=CACHE_TTL)
        logger.debug(f"Embedding cached: {cache_key}")

        # Record metrics
        record_metric(
            name="matching.encode_latency_ms",
            value=latency_ms,
            tags={"tenant_id": tenant_id or "none", "lang": lang}
        )
        record_metric(
            name="matching.encode_success",
            value=1,
            tags={"tenant_id": tenant_id or "none", "lang": lang}
        )

        return embedding

    except Exception as e:
        logger.error(f"Failed to encode text: {str(e)}")
        record_metric(
            name="matching.encode_failed",
            value=1,
            tags={"tenant_id": tenant_id or "none", "lang": lang, "error": str(e)}
        )
        raise EncoderError(f"Failed to encode text: {str(e)}")

def batch_encode_texts(texts: List[str], lang: str, tenant_id: Optional[str] = None) -> List[List[float]]:
    """
    Encode a batch of texts into embedding vectors.
    - Normalizes language code.
    - Uses cache for individual texts.
    - Optimizes with batch processing for uncached texts.
    Args:
        texts (List[str]): List of texts to encode.
        lang (str): Language code (BCP-47, e.g., 'fr', 'pt-br').
        tenant_id (str, optional): Tenant identifier.
    Returns:
        List[List[float]]: List of normalized embedding vectors.
    Raises:
        ValidationError: If inputs are invalid.
        EncoderError: If encoding fails.
    """
    try:
        # Validate inputs
        if not texts or not isinstance(texts, list) or not all(isinstance(t, str) and t.strip() for t in texts):
            logger.error("Invalid texts: must be a non-empty list of non-empty strings")
            raise ValidationError(_("Texts must be a non-empty list of non-empty strings"))
        lang = normalize_locale(lang)
        validate_lang(lang)
        if tenant_id:
            validate_tenant_id(tenant_id)

        # Check cache for individual texts
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        cache_keys = [
            f"matching:embed:{tenant_id or 'none'}:{lang}:{hashlib.sha256(t.encode('utf-8')).hexdigest()}"
            for t in texts
        ]

        for idx, (text, cache_key) in enumerate(zip(texts, cache_keys)):
            cached_embedding = cache.get(cache_key)
            if cached_embedding is not None:
                logger.debug(f"Cache hit for embedding: {cache_key}")
                record_metric(
                    name="matching.encode_cache_hit",
                    value=1,
                    tags={"tenant_id": tenant_id or "none", "lang": lang}
                )
                embeddings.append(cached_embedding)
            else:
                uncached_texts.append(text)
                uncached_indices.append(idx)
                embeddings.append(None)

        # Batch encode uncached texts
        if uncached_texts:
            model = load_model()
            start_time = time.time()
            batch_embeddings = model.encode(uncached_texts, normalize_embeddings=True).tolist()
            latency_ms = (time.time() - start_time) * 1000

            # Validate dimensions
            for embedding in batch_embeddings:
                if len(embedding) != EMBEDDING_DIM:
                    logger.error(f"Invalid embedding dimension: {len(embedding)}, expected {EMBEDDING_DIM}")
                    raise EncoderError(f"Invalid embedding dimension: {len(embedding)}")

            # Update embeddings and cache
            for idx, embedding, text, cache_key in zip(
                uncached_indices, batch_embeddings, uncached_texts, cache_keys
            ):
                embeddings[idx] = embedding
                cache.set(cache_key, embedding, timeout=CACHE_TTL)
                logger.debug(f"Embedding cached: {cache_key}")

            # Record batch metrics
            record_metric(
                name="matching.batch_encode_latency_ms",
                value=latency_ms,
                tags={"tenant_id": tenant_id or "none", "lang": lang, "batch_size": len(uncached_texts)}
            )
            record_metric(
                name="matching.batch_encode_success",
                value=len(uncached_texts),
                tags={"tenant_id": tenant_id or "none", "lang": lang}
            )

        return embeddings

    except Exception as e:
        logger.error(f"Failed to batch encode texts: {str(e)}")
        record_metric(
            name="matching.batch_encode_failed",
            value=1,
            tags={"tenant_id": tenant_id or "none", "lang": lang, "error": str(e)}
        )
        raise EncoderError(f"Failed to batch encode texts: {str(e)}")