# tests/test_urls.py
import pytest
from django.urls import reverse
from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework import status
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from unittest.mock import patch

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
def regular_user():
    return User.objects.create_user(username="user", email="user@example.com", password="user123", tenant_id="tenant_123")

@pytest.fixture
def client():
    return Client()

# Tests pour endpoints avec LANG_ENABLE_API
@pytest.mark.parametrize("endpoint,method,expected_status", [
    ("language:languages-list", "get", status.HTTP_200_OK),
    ("language:key-list", "get", status.HTTP_200_OK),
    ("language:translation-list", "get", status.HTTP_200_OK),
    ("language:job-list", "get", status.HTTP_200_OK),
])
def test_api_endpoints_enabled(client, superuser, endpoint, method, expected_status):
    """Teste les endpoints API avec LANG_ENABLE_API=True."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse(endpoint)
        response = getattr(client, method)(url)
        assert response.status_code == expected_status

def test_api_endpoints_disabled(client, superuser):
    """Teste que les endpoints sont désactivés si LANG_ENABLE_API=False."""
    with patch("django.conf.settings.LANG_ENABLE_API", False):
        client.force_login(superuser)
        url = reverse("language:languages-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

# Tests pour permissions
def test_api_endpoints_unauthenticated(client):
    """Teste l'accès non authentifié aux endpoints."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        url = reverse("language:languages-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_api_endpoints_regular_user(client, regular_user):
    """Teste l'accès pour utilisateur régulier (non staff)."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(regular_user)
        url = reverse("language:languages-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN  # Non staff
        url = reverse("language:key-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK  # Tenant match

# Tests pour actions spécifiques
@patch("transversales.language.tasks.run_translation_job")
def test_job_run_endpoint(mock_task, client, superuser):
    """Teste l'endpoint /jobs/<pk>/run/."""
    job = TranslationJobFactory.create(state="done")
    client.force_login(superuser)
    url = reverse("language:job-run", kwargs={"pk": job.id})
    response = client.post(url)
    assert response.status_code == status.HTTP_201_CREATED
    mock_task.delay.assert_called_once_with(job.id)
    assert response.json().get("task_id") is not None

def test_job_run_endpoint_running_denied(client, superuser):
    """Teste le refus si job running."""
    job = TranslationJobFactory.create(state="running")
    client.force_login(superuser)
    url = reverse("language:job-run", kwargs={"pk": job.id})
    response = client.post(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@patch("transversales.language.tasks.run_translation_job")
def test_job_run_endpoint_unauthenticated(client, mock_task):
    """Teste l'accès non authentifié à /jobs/<pk>/run/."""
    job = TranslationJobFactory.create()
    url = reverse("language:job-run", kwargs={"pk": job.id})
    response = client.post(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    mock_task.delay.assert_not_called()

def test_job_export_endpoint(client, superuser):
    """Teste l'endpoint /jobs/<pk>/export/."""
    job = TranslationJobFactory.create(stats={"per_lang": {"en": 5}}, errors=["Error 1"])
    client.force_login(superuser)
    url = reverse("language:job-export", kwargs={"pk": job.id})
    response = client.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert "text/csv" in response["Content-Type"]
    assert response["Content-Disposition"] == f'attachment; filename="job_{job.id}_results.csv"'

# Tests pour throttling
def test_language_throttle(client, superuser):
    """Teste le throttling à 200 requêtes/minute."""
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(superuser)
        url = reverse("language:languages-list")
        for _ in range(200):
            response = client.get(url)
            assert response.status_code == status.HTTP_200_OK
        response = client.get(url)  # 201e requête
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

# Tests pour tenant_id
def test_tenant_id_mismatch(client, regular_user):
    """Teste l'accès avec tenant_id non correspondant."""
    TranslatableKeyFactory.create(tenant_id="tenant_456")
    with patch("django.conf.settings.LANG_ENABLE_API", True):
        client.force_login(regular_user)  # tenant_id="tenant_123"
        url = reverse("language:key-list")
        response = client.get(url + "?tenant_id=tenant_456")
        assert response.status_code == status.HTTP_200_OK  # Liste vide (tenant mismatch)
        assert len(response.json()) == 0
        