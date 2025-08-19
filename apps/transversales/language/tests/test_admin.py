# tests/test_admin.py
import pytest
from unittest.mock import patch
from django.test import RequestFactory, Client
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from transversales.language.admin import LanguageAdmin, TranslatableKeyAdmin, TranslationAdmin, TranslationJobAdmin
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.utils import clear_lang_caches
import bleach

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
def admin_site():
    return AdminSite()

# Tests pour LanguageAdmin
def test_language_admin_activate(admin_site, superuser):
    """Teste l'action activate de LanguageAdmin."""
    language = LanguageFactory.create(is_active=False)
    request = RequestFactory().get('/')
    request.user = superuser
    language_admin = LanguageAdmin(Language, admin_site)
    
    with patch("transversales.language.utils.clear_lang_caches") as mock_clear:
        language_admin.activate(request, Language.objects.filter(id=language.id))
        language.refresh_from_db()
        assert language.is_active
        mock_clear.assert_called_once()

def test_language_admin_deactivate_default_denied(admin_site, superuser):
    """Teste que deactivate ne désactive pas la langue par défaut."""
    language = LanguageFactory.create(is_default=True)
    request = RequestFactory().get('/')
    request.user = superuser
    language_admin = LanguageAdmin(Language, admin_site)
    
    language_admin.deactivate(request, Language.objects.filter(id=language.id))
    language.refresh_from_db()
    assert language.is_active  # Langue par défaut reste active

# Tests pour TranslatableKeyAdmin
def test_translatable_key_admin_permissions(admin_site, regular_user, superuser):
    """Teste les permissions de TranslatableKeyAdmin."""
    key = TranslatableKeyFactory.create(tenant_id="tenant_123")
    request = RequestFactory().get('/')
    key_admin = TranslatableKeyAdmin(TranslatableKey, admin_site)
    
    request.user = regular_user
    assert key_admin.has_view_permission(request, key)
    assert key_admin.has_change_permission(request, key)
    
    request.user = superuser
    assert key_admin.has_view_permission(request, key)
    assert key_admin.has_change_permission(request, key)

# Tests pour TranslationAdmin
def test_translation_admin_short_text_xss(admin_site, superuser):
    """Teste la sanitisation XSS dans short_text de TranslationAdmin."""
    translation = TranslationFactory.create(text="<script>alert('xss')</script>")
    request = RequestFactory().get('/')
    request.user = superuser
    translation_admin = TranslationAdmin(Translation, admin_site)
    
    result = translation_admin.short_text(translation)
    assert "<script>" not in result
    assert bleach.clean(translation.text[:50], tags=bleach.ALLOWED_TAGS) in result

def test_translation_admin_permissions(admin_site, regular_user, superuser):
    """Teste les permissions de TranslationAdmin."""
    translation = TranslationFactory.create(tenant_id="tenant_123")
    request = RequestFactory().get('/')
    translation_admin = TranslationAdmin(Translation, admin_site)
    
    request.user = regular_user
    assert translation_admin.has_view_permission(request, translation)
    assert translation_admin.has_change_permission(request, translation)
    
    request.user = superuser
    assert translation_admin.has_view_permission(request, translation)
    assert translation_admin.has_change_permission(request, translation)

# Tests pour TranslationJobAdmin
@patch("transversales.language.tasks.run_batch_translation_items")
def test_translation_job_admin_rerun(mock_task, admin_site, superuser, client):
    """Teste l'action rerun_job de TranslationJobAdmin."""
    job = TranslationJobFactory.create(state="done")
    client.force_login(superuser)
    url = reverse("admin:language_translationjob_rerun", args=[job.id])
    
    response = client.post(url, follow=True)
    assert response.status_code == 200
    mock_task.delay.assert_called_once_with(
        item_ids=job.glossary_ids,
        source_lang=job.source_locale,
        target_langs=job.target_locales,
        tenant_id=job.tenant_id
    )

@patch("transversales.language.tasks.run_vectorize_scopes")
def test_translation_job_admin_vectorize(mock_task, admin_site, superuser):
    """Teste l'action vectorize_job de TranslationJobAdmin."""
    job = TranslationJobFactory.create()
    request = RequestFactory().get('/')
    request.user = superuser
    job_admin = TranslationJobAdmin(TranslationJob, admin_site)
    
    job_admin.vectorize_job(request, TranslationJob.objects.filter(id=job.id))
    mock_task.delay.assert_called_once_with(job.scope_filter, job.tenant_id)

def test_translation_job_admin_export_results(admin_site, superuser, client):
    """Teste l'action export_results de TranslationJobAdmin."""
    job = TranslationJobFactory.create(stats={"per_lang": {"en": 5}}, errors=["Error 1"])
    client.force_login(superuser)
    url = reverse("admin:language_translationjob_export", args=[job.id])
    
    response = client.post(url)
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert response["Content-Disposition"] == f'attachment; filename="job_{job.id}_results.csv"'

def test_translation_job_admin_permissions_denied(admin_site, regular_user):
    """Teste le refus d'accès pour utilisateur non-staff."""
    job = TranslationJobFactory.create()
    request = RequestFactory().get('/')
    request.user = regular_user
    job_admin = TranslationJobAdmin(TranslationJob, admin_site)
    
    with pytest.raises(PermissionDenied):
        job_admin.rerun_job(request, job.id)
    with pytest.raises(PermissionDenied):
        job_admin.export_results(request, job.id)
    with pytest.raises(PermissionDenied):
        job_admin.vectorize_job(request, TranslationJob.objects.filter(id=job.id))

