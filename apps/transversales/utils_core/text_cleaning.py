from __future__ import annotations
import re
import unicodedata
from typing import List, Optional
import numpy as np
from utils_core.errors import ValidationError

__all__ = ["normalize_text", "remove_accents", "strip_html", "standardize_whitespace", "normalize_text_batch"]

# Regex compilé pour performance
_HTML_RE = re.compile(r"<[^>]+>", re.UNICODE | re.IGNORECASE)

def normalize_text(text: str, remove_accents_flag: bool = False, case_sensitive: bool = False) -> str:
    """Normalize a text string for queries or prompts.

    Args:
        text: Input text to normalize.
        remove_accents_flag: If True, remove accents (default: False).
        case_sensitive: If False, convert to lowercase (default: False).

    Returns:
        str: Normalized text (stripped HTML, standardized whitespace, optional accents/case).

    Raises:
        ValidationError: If input is not a string.

    Example:
        >>> normalize_text("<p>Soudure  Inox  316L!</p>", remove_accents_flag=True)
        'soudure inox 316l'
    """
    if not isinstance(text, str):
        raise ValidationError(f"Input must be a string, got {type(text).__name__}")
    result = strip_html(text)
    result = standardize_whitespace(result)
    if remove_accents_flag:
        result = remove_accents(result)
    if not case_sensitive:
        result = result.lower()
    return result

def remove_accents(text: str) -> str:
    """Remove accents from a text string.

    Args:
        text: Input text.

    Returns:
        str: Text without accents.

    Raises:
        ValidationError: If input is not a string.

    Example:
        >>> remove_accents("Soudure Électrique")
        'Soudure Electrique'
    """
    if not isinstance(text, str):
        raise ValidationError(f"Input must be a string, got {type(text).__name__}")
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd_form if not unicodedata.combining(c))

def strip_html(text: str) -> str:
    """Remove HTML tags from a text string.

    Args:
        text: Input text containing HTML.

    Returns:
        str: Text without HTML tags.

    Raises:
        ValidationError: If input is not a string.

    Example:
        >>> strip_html("<p>Hello</p>")
        'Hello'
    """
    if not isinstance(text, str):
        raise ValidationError(f"Input must be a string, got {type(text).__name__}")
    return _HTML_RE.sub("", text)

def standardize_whitespace(text: str) -> str:
    """Replace multiple whitespaces with a single space.

    Args:
        text: Input text.

    Returns:
        str: Text with standardized whitespace.

    Raises:
        ValidationError: If input is not a string.

    Example:
        >>> standardize_whitespace("Hello   World")
        'Hello World'
    """
    if not isinstance(text, str):
        raise ValidationError(f"Input must be a string, got {type(text).__name__}")
    return " ".join(text.split())

def normalize_text_batch(texts: List[str], remove_accents_flag: bool = False, case_sensitive: bool = False) -> np.ndarray:
    """Normalize a batch of text strings using vectorized operations.

    Args:
        texts: List of input texts to normalize.
        remove_accents_flag: If True, remove accents (default: False).
        case_sensitive: If False, convert to lowercase (default: False).

    Returns:
        np.ndarray: Array of normalized texts.

    Raises:
        ValidationError: If input is not a list of strings.

    Example:
        >>> normalize_text_batch(["<p>Soudure  Inox</p>", "Électrique"], remove_accents_flag=True)
        array(['soudure inox', 'electrique'], dtype='<U13')
    """
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        raise ValidationError("Input must be a list of strings")
    
    # Convert to NumPy array for vectorized operations
    texts_array = np.array(texts, dtype=str)
    
    # Strip HTML
    texts_array = np.vectorize(lambda x: _HTML_RE.sub("", x))(texts_array)
    
    # Standardize whitespace
    texts_array = np.vectorize(lambda x: " ".join(x.split()))(texts_array)
    
    # Remove accents if requested
    if remove_accents_flag:
        texts_array = np.vectorize(
            lambda x: "".join(c for c in unicodedata.normalize("NFKD", x) if not unicodedata.combining(c))
        )(texts_array)
    
    # Convert to lowercase if not case-sensitive
    if not case_sensitive:
        texts_array = np.vectorize(str.lower)(texts_array)
    
    return texts_array