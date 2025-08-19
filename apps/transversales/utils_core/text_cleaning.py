# utils_core/text_cleaning.py
from __future__ import annotations

import html
import re
import unicodedata
from typing import Iterable

__all__ = [
    "normalize_text",
    "remove_accents",
    "strip_html",
    "standardize_whitespace",
]

# ──────────────────────────────────────────────────────────────────────────────
# Regex précompilées (performance)
# ──────────────────────────────────────────────────────────────────────────────

# <script> / <style> (supprimer avec contenu)
_RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")

# Tags HTML génériques
_RE_TAGS = re.compile(r"(?s)<[^>]*>")

# <br>, </p>, </div>, </li> → sauts de ligne si keep_linebreaks=True
_RE_BREAK_TAGS = re.compile(r"(?is)<br\s*/?>|</p>|</div>|</li>")

# Tout type d'espace unicode (y compris tab, nbsp…) en un seul espace
_RE_MULTI_WS = re.compile(r"[ \t\r\f\v]+")

# Séquences de lignes vides > 2 → 2 lignes max
_RE_MULTI_NL = re.compile(r"\n{3,}")

# ──────────────────────────────────────────────────────────────────────────────
# Tables de traduction des espaces “exotiques”
# ──────────────────────────────────────────────────────────────────────────────

# Espaces “visibles” à ramener à un espace simple
_SPACE_LIKE: Iterable[str] = (
    "\u00A0",  # NO-BREAK SPACE
    "\u1680",  # OGHAM SPACE MARK
    "\u180E",  # MONGOLIAN VOWEL SEPARATOR (déprécié)
    "\u2000",  # EN QUAD
    "\u2001",  # EM QUAD
    "\u2002",  # EN SPACE
    "\u2003",  # EM SPACE
    "\u2004",  # THREE-PER-EM SPACE
    "\u2005",  # FOUR-PER-EM SPACE
    "\u2006",  # SIX-PER-EM SPACE
    "\u2007",  # FIGURE SPACE
    "\u2008",  # PUNCTUATION SPACE
    "\u2009",  # THIN SPACE
    "\u200A",  # HAIR SPACE
    "\u202F",  # NARROW NO-BREAK SPACE
    "\u205F",  # MEDIUM MATHEMATICAL SPACE
    "\u3000",  # IDEOGRAPHIC SPACE
)

# Espaces “zéro” à supprimer
_ZERO_WIDTH: Iterable[str] = (
    "\u200B",  # ZERO WIDTH SPACE
    "\u200C",  # ZERO WIDTH NON-JOINER
    "\u200D",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\uFEFF",  # ZERO WIDTH NO-BREAK SPACE (BOM)
)

_SPACE_TABLE = str.maketrans({c: " " for c in _SPACE_LIKE} | {c: "" for c in _ZERO_WIDTH})

# ──────────────────────────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────────────────────────

def standardize_whitespace(text: str, *, keep_newlines: bool = False) -> str:
    """
    Standardise les espaces (y compris Unicode) et lignes vides.
    - Espaces multiples → espace unique.
    - Espaces "exotiques" (nbsp, en-space…) → espace standard.
    - Espaces zéro-largeur → supprimés.
    - Lignes vides multiples → max 2 si keep_newlines=True.
    """
    if not text:
        return ""

    t = text.translate(_SPACE_TABLE)
    t = _RE_MULTI_WS.sub(" ", t)
    if keep_newlines:
        t = _RE_MULTI_NL.sub("\n\n", t)
    else:
        t = t.replace("\n", " ")
    return t.strip()

def strip_html(text: str, *, keep_linebreaks: bool = False) -> str:
    """
    Supprime le HTML et unescape les entités.
    - Supprime <script>/<style> (y compris contenu).
    - Supprime les autres tags.
    - <br>, </p>, </div>, </li> → \n si keep_linebreaks=True.
    - Unescape entités HTML après suppression.
    """
    if not text:
        return ""

    t = str(text)
    t = _RE_SCRIPT_STYLE.sub("", t)
    if keep_linebreaks:
        t = _RE_BREAK_TAGS.sub("\n", t)
    t = _RE_TAGS.sub("", t)
    return html.unescape(t)

def remove_accents(text: str, *, form: str = "NFKD") -> str:
    """
    Supprime les diacritiques via normalisation Unicode.
    Par défaut NFKD (décomposition + compatibilité), puis filtre les combining marks.
    """
    if not text:
        return ""

    normalized = unicodedata.normalize(form, text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

def normalize_text(
    text: str,
    *,
    lowercase: bool = True,
    strip_html_first: bool = True,
    keep_linebreaks: bool = False,
    remove_accents_flag: bool = True,
    unicode_form: str = "NFKC",
) -> str:
    """
    Pipeline de normalisation “sûr par défaut” pour préparer les textes avant traitement.
    - Utilisé dans matching pour normaliser les queries avant encodage (services.encode_texts).
    - Utilisé dans language pour normaliser source_text avant traduction (services.batch_translate_scope).
    - Utilisé dans LLM_ai pour nettoyer les prompts avant appels (services.translate_text).
    - Potentiellement utilisé dans dico pour normaliser les labels/concepts.

    Ordre:
      (1) HTML → texte (optionnel),
      (2) unescape entités,
      (3) standardisation des espaces,
      (4) normalisation Unicode,
      (5) suppression des accents (optionnel),
      (6) passage en minuscules (optionnel).

    Args:
        text (str): Texte à normaliser.
        lowercase: Met en minuscules en fin de pipeline.
        strip_html_first: Retire le HTML avant les autres étapes.
        keep_linebreaks: Conserve des sauts de ligne propres.
        remove_accents_flag: Supprime les diacritiques.
        unicode_form: Forme de normalisation Unicode finale (ex. "NFKC", "NFC").

    Returns:
        str: Texte normalisé.

    Examples:
        >>> from utils_core.text_cleaning import normalize_text
        >>> normalize_text("<p>Soudure Inox 316L aéronautique</p>", remove_accents_flag=True)
        'soudure inox 316l aeronautique'  # matching: query
        >>> normalize_text("Café français", remove_accents_flag=False, lowercase=False)
        'Café français'  # language: source_text
        >>> normalize_text("Text<br>with\nlinebreaks", keep_linebreaks=True)
        'text\nwith\nlinebreaks'  # curation: validation
    """
    if text is None:
        return ""

    t = str(text)

    if strip_html_first:
        t = strip_html(t, keep_linebreaks=keep_linebreaks)
    else:
        # Si le HTML est déjà absent, au moins unescape les entités HTML
        t = html.unescape(t)

    t = standardize_whitespace(t, keep_newlines=keep_linebreaks)

    # Normalisation Unicode finale
    t = unicodedata.normalize(unicode_form, t)

    if remove_accents_flag:
        # Garder la forme unicode choisie après suppression des accents
        t = remove_accents(t, form="NFKD")
        t = unicodedata.normalize(unicode_form, t)

    if lowercase:
        t = t.lower()

    return t
    