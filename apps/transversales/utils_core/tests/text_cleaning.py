import pytest
from utils_core.text_cleaning import normalize_text, remove_accents, strip_html, standardize_whitespace

def test_normalize_text_nominal():
    """Teste la normalisation d'un texte standard."""
    text = "<p>Soudure Inox 316L aéronautique</p>"
    result = normalize_text(text, remove_accents_flag=True)
    assert result == "soudure inox 316l aeronautique"

def test_normalize_text_accents():
    """Teste la conservation des accents si demandé."""
    text = "Café français"
    result = normalize_text(text, remove_accents_flag=False, lowercase=False)
    assert result == "Café français"

def test_normalize_text_linebreaks():
    """Teste la conservation des sauts de ligne."""
    text = "Text<br>with\nlinebreaks"
    result = normalize_text(text, keep_linebreaks=True)
    assert result == "text\nwith\nlinebreaks"

def test_normalize_text_empty():
    """Teste un texte vide ou None."""
    assert normalize_text("") == ""
    assert normalize_text(None) == ""