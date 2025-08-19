from __future__ import annotations
from typing import Any, Optional
from hashlib import sha256
from .time_utils import timer
from .decorators import retry_on_exception
from .text_cleaning import normalize_text

__all__ = ["compute_checksum", "slugify", "normalize_text", "timer", "retry_on_exception"]

def compute_checksum(text: str, algo: str = "sha256") -> str:
    """Compute a checksum for a given text using the specified algorithm.

    Args:
        text: Input text to hash.
        algo: Hash algorithm (default: 'sha256').

    Returns:
        str: Hexadecimal checksum.

    Example:
        >>> compute_checksum("Soudure inox 316L")
        'a1b2c3d4e5f6...'  # SHA256 hash
    """
    if algo != "sha256":
        raise ValueError(f"Unsupported algorithm: {algo}")
    return sha256(text.encode("utf-8")).hexdigest()

def slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Args:
        text: Input text to slugify.

    Returns:
        str: URL-safe slug.

    Example:
        >>> slugify("Soudure Inox 316L")
        'soudure-inox-316l'
    """
    text = text.lower().strip()
    text = "".join(c if c.isalnum() or c == " " else "-" for c in text)
    text = "-".join(word for word in text.split() if word)
    return text.replace("--", "-").rstrip("-")