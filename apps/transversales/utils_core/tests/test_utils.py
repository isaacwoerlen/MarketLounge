import pytest
from django.core.exceptions import ValidationError
from utils_core.utils import compute_checksum, retry_on_exception
from utils_core.constants import RETRY_MAX_ATTEMPTS

def test_compute_checksum_nominal():
    """Teste un texte standard."""
    text = "soudure inox 316L"
    expected = "3f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b"  # Exemple (hash réel à calculer)
    assert compute_checksum(text) == expected
    assert len(compute_checksum(text)) == 64  # SHA256 = 64 hex chars

def test_compute_checksum_empty():
    """Teste une chaîne vide."""
    assert compute_checksum("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert len(compute_checksum("")) == 64

def test_compute_checksum_accents():
    """Teste un texte avec accents."""
    text = "soudure aéronautique française"
    result = compute_checksum(text)
    assert len(result) == 64
    assert result == compute_checksum(text)  # Idempotence

def test_compute_checksum_invalid_type():
    """Teste un input non-string."""
    with pytest.raises(ValueError, match="Text must be a string"):
        compute_checksum(123)
    with pytest.raises(ValueError, match="Text must be a string"):
        compute_checksum(None)

def test_retry_on_exception_success():
    """Teste retry_on_exception avec succès immédiat."""
    @retry_on_exception(exception_types=ValueError, max_attempts=2)
    def success_func():
        return "success"
    assert success_func() == "success"

def test_retry_on_exception_retry():
    """Teste retry_on_exception avec retries réussis."""
    attempts = 0
    @retry_on_exception(exception_types=ValueError, max_attempts=3)
    def retry_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Retry")
        return "success"
    assert retry_func() == "success"
    assert attempts == 3

def test_retry_on_exception_failure():
    """Teste retry_on_exception avec échec final."""
    @retry_on_exception(exception_types=ValueError, max_attempts=2)
    def fail_func():
        raise ValueError("Fail")
    with pytest.raises(ValueError, match="Fail"):
        fail_func()