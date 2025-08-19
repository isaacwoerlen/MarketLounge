# tests/test_views.py
import pytest
from unittest.mock import patch
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from django.core.exceptions import ValidationError
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.serializers import TranslationSerializer, TranslationCreateSerializer, TranslationJobSerializer
from transversales.language.views import LanguageViewSet, TranslatableKeyViewSet, TranslationViewSet, TranslationJobViewSet

pytestmark = pytest.mark.django_db

User = get_user_model()

# Factories pour données de test
class LanguageFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "code": "fr",
            "name": "Français",
            "is_active": True,
            "is_default": True,
            "priority": 1,
        }
        defaults.update(kwargs)
        return Language.objects.create(**defaults)

class TranslatableKeyFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "scope": "glossary",
            "key": "label",
            "tenant_id": "tenant_123",
        }
        defaults.update(kwargs)
        return TranslatableKey.objects.create(**defaults)

class TranslationFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "text": "Étiquette",
            "source_checksum": "checksum",
            "origin": "human",
            "tenant_id": "tenant_123",
        }
        defaults.update(kwargs)
        if "key" not in defaults:
            defaults["key"] = TranslatableKeyFactory.create()
        if "language" not in defaults:
            defaults["language"] = LanguageFactory.create()
        return Translation.objects.create(**defaults)

class TranslationJobFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "name": "Test Job",
            "state": "queued",
            "source_locale": "fr",
            "target_locales": ["en"],
            "scope_filter": ["glossary"],
            "stats": {"processed": 0, "per_lang": {"en": 0}},
            "tenant_id": "tenant_123",
        }
        defaults.update(kwargs)
        return TranslationJob.objects.create(**defaults)

# Fixtures pour utilisateurs
@pytest.fixture
def superuser():
    return User.objects.create_superuser(username="admin", email="admin@example.com", password="admin123")

@pytest.fixture
def staff_user():
    return User.objects.create_user(username="staff", email="staff@example.com", password="staff123", is_staff=True)

@pytest.fixture
def regular_user():
    return User.objects.create_user(username="user", email="user@example.com", password="user123", tenant_id="tenant_123")

@pytest.fixture
def client():
    return Client()

# Tests pour LanguageViewSet
def test_language_viewset_list(client, superuser):
    """Teste l'endpoint GET /languages/."""
    LanguageFactory.create(code="en", is_default=False)
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:languages-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1
        assert response.json()[0]["code"] in ["fr", "en"]

def test_language_viewset_unauthenticated(client):
    """Teste l'accès non authentifié à /languages/."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        url = reverse("language:languages-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

# Tests pour TranslatableKeyViewSet
def test_translatable_key_viewset_list(client, regular_user):
    """Teste l'endpoint GET /keys/ avec tenant_id."""
    TranslatableKeyFactory.create(tenant_id="tenant_123")
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(regular_user)
        url = reverse("language:key-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["tenant_id"] == "tenant_123"

def test_translatable_key_viewset_create(client, superuser):
    """Teste l'endpoint POST /keys/."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:key-list")
        data = {"scope": "seo", "key": "title", "tenant_id": "tenant_456"}
        response = client.post(url, data, content_type="application/json")
        assert response.status_code == status.HTTP_201_CREATED
        assert TranslatableKey.objects.filter(scope="seo", key="title").exists()

# Tests pour TranslationViewSet
@patch("transversales.language.views.store_translation")
def test_translation_viewset_create(mock_store, client, superuser):
    """Teste l'endpoint POST /translations/."""
    key = TranslatableKeyFactory.create()
    LanguageFactory.create(code="en", is_default=False)
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:translation-list")
        data = {
            "key": key.id,
            "target_lang": "en",
            "translated_text": "Label",
            "source_text": "Étiquette",
        }
        response = client.post(url, data, content_type="application/json")
        assert response.status_code == status.HTTP_201_CREATED
        mock_store.assert_called_once()

@patch("transversales.language.views.TranslationSerializer")
def test_translation_viewset_review(mock_serializer, client, superuser):
    """Teste l'action /translations/<pk>/review/."""
    translation = TranslationFactory.create()
    mock_serializer.return_value.is_valid.return_value = True
    mock_serializer.return_value.save.return_value = translation
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:translation-review", kwargs={"pk": translation.id})
        response = client.post(url, {"text": "New Label"}, content_type="application/json")
        assert response.status_code == status.HTTP_200_OK
        mock_serializer.assert_called_once()

# Tests pour TranslationJobViewSet
@patch("transversales.language.tasks.run_translation_job")
def test_translation_job_viewset_create(mock_task, client, superuser):
    """Teste l'endpoint POST /jobs/."""
    LanguageFactory.create(code="en", is_default=False)
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:job-list")
        data = {
            "name": "Test Job",
            "source_locale": "fr",
            "target_locales": ["en"],
            "scope_filter": ["glossary"],
            "tenant_id": "tenant_123",
        }
        response = client.post(url, data, content_type="application/json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json().get("task_id") is not None
        mock_task.delay.assert_called_once()

@patch("transversales.language.tasks.run_vectorize_scopes")
def test_translation_job_viewset_vectorize(mock_task, client, superuser):
    """Teste l'action /jobs/<pk>/vectorize/."""
    job = TranslationJobFactory.create()
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:job-vectorize", kwargs={"pk": job.id})
        response = client.post(url)
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json().get("queued") is True
        mock_task.delay.assert_called_once_with(job.scope_filter, job.tenant_id)

def test_translation_job_viewset_permissions(client, regular_user):
    """Teste les permissions pour /jobs/."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(regular_user)
        url = reverse("language:job-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN  # Non staff

# Tests pour throttling
def test_translation_viewset_throttle(client, superuser):
    """Teste le throttling à 200 requêtes/minute."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:translation-list")
        for _ in range(200):
            response = client.get(url)
            assert response.status_code == status.HTTP_200_OK
        response = client.get(url)  # 201e requête
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
