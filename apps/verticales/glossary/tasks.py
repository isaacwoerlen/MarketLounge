# apps/glossary/tasks.py
import os
import json
import time
import math
import hashlib
import logging
from contextlib import contextmanager

import numpy as np
import redis
import faiss

from celery import shared_task
from django.core.management import call_command
from django.db.models import Q

from apps.glossary.models import GlossaryNode

logger = logging.getLogger(__name__)

# --- Config via env (avec valeurs par défaut sûres) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "/app/faiss/index.bin")
FAISS_META_PATH = os.getenv("FAISS_META_PATH", "/app/faiss/meta.json")
FAISS_DIM = int(os.getenv("FAISS_DIM", "384"))  # MiniLM/E5 ~ 384 dims (cf. archi)
FAISS_CHUNK = int(os.getenv("FAISS_CHUNK", "2048"))  # taille des batchs lors du build

# --- Helpers ---
def _redis():
    return redis.Redis.from_url(REDIS_URL)

@contextmanager
def redis_lock(key: str, ttl: int = 3600):
    r = _redis()
    ok = r.set(key, str(time.time()), nx=True, ex=ttl)
    try:
        if not ok:
            raise RuntimeError(f"Lock '{key}' already held")
        yield
    finally:
        try:
            r.delete(key)
        except Exception:
            pass

def _glossary_id_to_int64(glossary_id: str) -> int:
    """ID FAISS stable à partir d'un glossary_id string."""
    # 8 octets -> int64 positif
    h = hashlib.blake2b(glossary_id.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, byteorder="big", signed=False) & ((1 << 63) - 1)

def _normalize_rows(mat: np.ndarray) -> np.ndarray:
    # normalisation L2 par rangée (pour cosine via dot)
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return (mat / norms).astype("float32")

# --- Tasks ---
@shared_task
def run_generate_glossary(glossary_ids):
    """
    Déclenche la commande 'generate_glossary' pour une liste d'IDs.
    Loggue les erreurs, ne les avale pas silencieusement.
    """
    if not glossary_ids:
        logger.info("run_generate_glossary: no ids")
        return {"processed": 0, "errors": 0}

    processed = 0
    errors = 0
    seen = set()
    for gid in glossary_ids:
        if not gid or gid in seen:
            continue
        seen.add(gid)
        try:
            call_command("generate_glossary", gid)
            processed += 1
        except Exception as e:
            logger.exception("generate_glossary failed for %s: %s", gid, e)
            errors += 1
    return {"processed": processed, "errors": errors}

@shared_task
def monthly_glossary_scan():
    """
    Scan mensuel: enrichit tous les nœuds 'pending IA'.
    Protégé par un lock Redis pour éviter les overlaps.
    """
    try:
        with redis_lock("locks:glossary_scan", ttl=3_600):
            call_command("generate_glossary", all_pending=True)
            return {"status": "ok"}
    except Exception as e:
        logger.exception("monthly_glossary_scan error: %s", e)
        return {"status": "error", "detail": str(e)}

@shared_task
def sync_embeddings_to_faiss():
    """
    Rebuild complet de l'index FAISS depuis les embeddings en base (pgvector).
    - Cosine via IndexFlatIP avec vecteurs normalisés
    - IDs stables (int64) mappés à glossary_id
    - Écriture atomique (tmp + rename)
    - Lock Redis anti-concurrence
    """
    try:
        with redis_lock("locks:faiss_build", ttl=3_600):
            qs = GlossaryNode.objects.filter(~Q(embedding=None))
            total = qs.count()
            if total == 0:
                logger.info("FAISS build: no vectors")
                # Ecrire un index vide
                index = faiss.IndexIDMap2(faiss.IndexFlatIP(FAISS_DIM))
                faiss.write_index(index, FAISS_INDEX_PATH)
                with open(FAISS_META_PATH, "w", encoding="utf-8") as f:
                    json.dump({"count": 0, "dim": FAISS_DIM, "metric": "cosine"}, f)
                return {"status": "ok", "count": 0}

            index = faiss.IndexIDMap2(faiss.IndexFlatIP(FAISS_DIM))
            id_map = {}  # int64 -> glossary_id

            # Build en chunks pour limiter la RAM
            pages = math.ceil(total / FAISS_CHUNK)
            cursor = 0
            while cursor < total:
                batch = list(
                    qs.order_by("glossary_id")
                      .only("glossary_id", "embedding")
                      [cursor : cursor + FAISS_CHUNK]
                )
                if not batch:
                    break
                vecs = np.array([n.embedding for n in batch], dtype="float32")
                vecs = _normalize_rows(vecs)
                ids = np.array([_glossary_id_to_int64(n.glossary_id) for n in batch], dtype="int64")
                index.add_with_ids(vecs, ids)
                id_map.update({int(i): b.glossary_id for i, b in zip(ids, batch)})
                cursor += FAISS_CHUNK

            # Écriture atomique
            tmp_idx = FAISS_INDEX_PATH + ".tmp"
            faiss.write_index(index, tmp_idx)
            os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
            os.replace(tmp_idx, FAISS_INDEX_PATH)

            meta = {
                "count": total,
                "dim": FAISS_DIM,
                "metric": "cosine",
                "updated_at": int(time.time()),
            }
            os.makedirs(os.path.dirname(FAISS_META_PATH), exist_ok=True)
            tmp_meta = FAISS_META_PATH + ".tmp"
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump({"meta": meta, "id_map": id_map}, f, ensure_ascii=False)
            os.replace(tmp_meta, FAISS_META_PATH)

            _redis().set("faiss:last_build_ts", meta["updated_at"])
            logger.info("FAISS build: %s vectors -> %s", total, FAISS_INDEX_PATH)
            return {"status": "ok", "count": total}
    except Exception as e:
        logger.exception("sync_embeddings_to_faiss error: %s", e)
        return {"status": "error", "detail": str(e)}
