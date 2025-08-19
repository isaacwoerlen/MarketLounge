# apps/transversales/language/tests/conftest.py
import pytest
import numpy as np
from django.core.cache import cache
from unittest.mock import patch
from transversales.language.tests.factories import LanguageFactory

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield

@pytest.fixture
def mock_encode_text():
    with patch("transversales.matching.services.encode_text", return_value=list(np.random.rand(384))) as mock:
        yield mock

@pytest.fixture
def mock_translate_text():
    with patch("transversales.LLM_ai.services.translate_text", return_value="Translated text") as mock:
        yield mock

@pytest.fixture
def mock_celery():
    with patch("transversales.language.tasks.run_batch_translation_items") as mock_items, \
         patch("transversales.language.tasks.run_batch_translation_scope") as mock_scope, \
         patch("transversales.language.tasks.run_vectorize_scopes") as mock_vectorize:
        mock_items.delay.return_value.id = "task-items-123"
        mock_scope.delay.return_value.id = "task-scope-123"
        mock_vectorize.delay.return_value.id = "task-vectorize-123"
        yield mock_items, mock_scope, mock_vectorize

@pytest.fixture
def default_language():
    language = LanguageFactory(code="fr", name="Français", is_active=True, is_default=True)
    yield language
    Language.objects.filter(code="fr").delete()  # Nettoyage
    