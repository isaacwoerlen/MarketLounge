# utils_core/utils.py
from django.utils.translation import gettext_lazy as _
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Callable, TypeVar, Type
from utils_core.constants import RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY_SEC
import re
import time

# Ré-exports pour DX
from utils_core.text_cleaning import normalize_text  # noqa: F401
from utils_core.metrics import log_metric  # noqa: F401

__all__ = [
    "compute_checksum",
    "retry_on_exception",
    "slugify",
    "Timer",
    "normalize_text",
    "log_metric",
]

T = TypeVar("T")

def compute_checksum(text: str) -> str:
    """
    Calcule un checksum SHA256 pour un texte donné, utilisé pour l'idempotence.
    - Normalise en supprimant les espaces de début/fin.
    - Encode en UTF-8 pour cohérence.
    - Utilisé dans language (Translation.source_checksum), matching (EmbeddingItem.checksum), 
      et potentiellement dico (concepts).

    Args:
        text (str): Texte à hasher.

    Returns:
        str: Hash SHA256 en hexadécimal (64 caractères).

    Raises:
        ValueError: Si l'entrée n'est pas une chaîne de caractères.

    Examples:
        >>> from utils_core.utils import compute_checksum
        >>> compute_checksum("soudure inox 316L")  # language: Translation.source_checksum
        '3f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b'
        >>> compute_checksum("concept_42")  # dico: concept checksum
        'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2'
    """
    if not isinstance(text, str):
        raise ValueError(_("Text must be a string"))
    text = text.strip() if text else ""
    return hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest()

def retry_on_exception(
    exception_types: Type[Exception] | tuple[Type[Exception], ...] = Exception,
    max_attempts: int | None = None,
    base_delay: float | None = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Décorateur pour réessayer une fonction en cas d'erreur transitoire.
    - Utilise tenacity pour retries avec backoff exponentiel.
    - Configuré via constants.RETRY_MAX_ATTEMPTS et RETRY_BASE_DELAY_SEC par défaut.
    - Utilisé pour appels LLM (language, LLM_ai), encodage (matching), ou tâches Celery.

    Args:
        exception_types: Type(s) d'exception(s) à réessayer (par défaut : Exception).
        max_attempts: Nombre max de tentatives (par défaut : RETRY_MAX_ATTEMPTS).
        base_delay: Délai initial en secondes (par défaut : RETRY_BASE_DELAY_SEC).

    Returns:
        Callable: Fonction décorée avec logique de retry.

    Example:
        >>> from utils_core.utils import retry_on_exception
        >>> @retry_on_exception(exception_types=(LLMError, TimeoutError), max_attempts=3)
        ... def call_llm(): ...  # language: safe_translate_text
        >>> @retry_on_exception(exception_types=EncoderError)
        ... def encode_texts(): ...  # matching: encode_texts
    """
    max_attempts = max_attempts or RETRY_MAX_ATTEMPTS
    base_delay = base_delay or RETRY_BASE_DELAY_SEC

    return retry(
        retry=retry_if_exception_type(exception_types),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=base_delay, min=base_delay, max=10.0)
    )

def slugify(text: str) -> str:
    """
    Convertit un texte en slug URL-safe (minuscules, tirets, alphanum).
    - Utilisé pour générer des identifiants lisibles dans curation (ex. : validation slugs),
      market (ex. : URL-friendly names), et language (ex. : SEO keywords).

    Args:
        text (str): Texte à transformer.

    Returns:
        str: Slug normalisé.

    Examples:
        >>> from utils_core.utils import slugify
        >>> slugify("Soudure Inox 316L")  # curation: validation slug
        'soudure-inox-316l'
        >>> slugify("Café français")  # market: URL name
        'cafe-francais'
    """
    text = normalize_text(text, remove_accents_flag=True, lowercase=True)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text

class Timer:
    """
    Contexte pour mesurer la durée d'exécution (en millisecondes).
    - Utilisé pour monitorer les performances dans matching (ex. : encodage),
      language (ex. : traduction batch), et LLM_ai (ex. : appels API).

    Example:
        >>> from utils_core.utils import Timer
        >>> with Timer() as t:
        ...     # opération coûteuse
        ...     pass
        >>> print(t.elapsed_ms)  # language: mesurer traduction
        123.45
    """
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end = time.perf_counter()
        self.elapsed_ms = (self.end - self.start) * 1000.0