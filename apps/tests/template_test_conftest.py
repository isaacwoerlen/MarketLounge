# apps/<app_name>/tests/conftest.py
import pytest
from django.core.cache import cache
from django.test import Client
from unittest.mock import patch
from django.contrib.auth import get_user_model
from faiss_pgvector.embeddings import encode_text
from <app_name>.tests.factories import <ModelName1>Factory, <ModelName2>Factory

@pytest.fixture(autouse=True)
def clear_cache():
    """Nettoie le cache avant chaque test."""
    cache.clear()
    yield

@pytest.fixture
def authenticated_client():
    """Fournit un client authentifié pour tester les vues."""
    user = get_user_model().objects.create_user(username='testuser', password='testpass')
    client = Client()
    client.login(username='testuser', password='testpass')
    return client

@pytest.fixture
def mock_mistral_client():
    """Mocke l'API Mistral (via LLM_ai)."""
    with patch('<app_name>.services.MistralClient') as mock:
        mock.return_value.translate.return_value = "Translated text"
        yield mock

@pytest.fixture
def mock_encode_text():
    """Mocke encode_text de faiss_pgvector."""
    with patch('faiss_pgvector.embeddings.encode_text') as mock:
        mock.return_value = b'mocked_vector'
        yield mock

@pytest.fixture
def default_language():
    """Fournit une langue par défaut."""
    return LanguageFactory(code='en', name='English', is_default=True, is_active=True)

@pytest.fixture
def translation_job():
    """Fournit un TranslationJob pour tests de tâches."""
    return TranslationJobFactory()