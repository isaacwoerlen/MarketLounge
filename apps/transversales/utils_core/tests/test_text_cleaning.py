import pytest
import numpy as np
from utils_core.text_cleaning import (
    normalize_text,
    remove_accents,
    strip_html,
    standardize_whitespace,
    normalize_text_batch,
)
from utils_core.errors import ValidationError

def test_normalize_text_basic():
    """Test normalize_text with basic input."""
    text = "<p>Soudure  Inox  316L!</p>"
    assert normalize_text(text) == "Soudure Inox 316L"
    assert normalize_text(text, remove_accents_flag=True) == "soudure inox 316l"
    assert normalize_text(text, case_sensitive=True) == "Soudure Inox 316L"

def test_normalize_text_invalid_input():
    """Test normalize_text with invalid input."""
    with pytest.raises(ValidationError, match="Input must be a string"):
        normalize_text(123)

def test_remove_accents_basic():
    """Test remove_accents with accented text."""
    assert remove_accents("Soudure Électrique") == "Soudure Electrique"
    assert remove_accents("Café") == "Cafe"

def test_remove_accents_invalid_input():
    """Test remove_accents with invalid input."""
    with pytest.raises(ValidationError, match="Input must be a string"):
        remove_accents(123)

def test_strip_html_basic():
    """Test strip_html with HTML input."""
    assert strip_html("<p>Hello</p>") == "Hello"
    assert strip_html("<div>Text <b>Bold</b></div>") == "Text Bold"

def test_strip_html_invalid_input():
    """Test strip_html with invalid input."""
    with pytest.raises(ValidationError, match="Input must be a string"):
        strip_html(123)

def test_standardize_whitespace_basic():
    """Test standardize_whitespace with multiple spaces."""
    assert standardize_whitespace("Hello   World") == "Hello World"
    assert standardize_whitespace("  Text\t\n  ") == "Text"

def test_standardize_whitespace_invalid_input():
    """Test standardize_whitespace with invalid input."""
    with pytest.raises(ValidationError, match="Input must be a string"):
        standardize_whitespace(123)

def test_normalize_text_batch_basic():
    """Test normalize_text_batch with valid inputs."""
    texts = ["<p>Soudure  Inox</p>", "Électrique"]
    result = normalize_text_batch(texts, remove_accents_flag=True)
    expected = np.array(["soudure inox", "electrique"])
    np.testing.assert_array_equal(result, expected)

def test_normalize_text_batch_case_sensitive():
    """Test normalize_text_batch with case-sensitive option."""
    texts = ["Soudure  Inox", "Électrique"]
    result = normalize_text_batch(texts, remove_accents_flag=True, case_sensitive=True)
    expected = np.array(["Soudure Inox", "Electrique"])
    np.testing.assert_array_equal(result, expected)

def test_normalize_text_batch_invalid_input():
    """Test normalize_text_batch with invalid input."""
    with pytest.raises(ValidationError, match="Input must be a list of strings"):
        normalize_text_batch(["text", 123])
    with pytest.raises(ValidationError, match="Input must be a list of strings"):
        normalize_text_batch("not a list")