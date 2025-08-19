# tests/test_permissions.py
import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import override_settings
from transversales.language.permissions import (
    can_view_language, can_change_language, can_delete_language,
    can_view_translatable_key, can_change_translatable_key,
    can_view_translation, can_change_translation,
    can_view_translation_job, can_rerun_translation_job, can_export_translation_job
)
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob

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
def anonymous_user():
    return User()

# Tests pour can_view_language
def test_can_view_language(superuser, staff_user, regular_user, anonymous_user):
    """Teste can_view_language pour différents utilisateurs."""
    language = LanguageFactory.create()
    
    assert can_view_language(superuser, language)
    assert can_view_language(staff_user, language)
    assert not can_view_language(regular_user, language)
    assert not can_view_language(anonymous_user, language)

# Tests pour can_change_language
def test_can_change_language(superuser, staff_user, regular_user):
    """Teste can_change_language pour différents utilisateurs."""
    language = LanguageFactory.create()
    
    assert can_change_language(superuser, language)
    assert can_change_language(staff_user, language)
    assert not can_change_language(regular_user, language)

# Tests pour can_delete_language
def test_can_delete_language(superuser, staff_user, regular_user):
    """Teste can_delete_language pour langue par défaut et non par défaut."""
    default_lang = LanguageFactory.create(is_default=True)
    non_default_lang = LanguageFactory.create(code="en", is_default=False)
    
    assert can_delete_language(superuser, default_lang)  # Superuser peut supprimer
    assert can_delete_language(superuser, non_default_lang)
    assert not can_delete_language(staff_user, default_lang)  # Staff ne peut pas supprimer default
    assert can_delete_language(staff_user, non_default_lang)
    assert not can_delete_language(regular_user, non_default_lang)

# Tests pour can_view_translatable_key
def test_can_view_translatable_key(superuser, staff_user, regular_user):
    """Teste can_view_translatable_key avec multi-tenancy."""
    key = TranslatableKeyFactory.create(tenant_id="tenant_123")
    other_key = TranslatableKeyFactory.create(tenant_id="tenant_456")
    
    assert can_view_translatable_key(superuser, key)
    assert can_view_translatable_key(staff_user, key)
    assert can_view_translatable_key(regular_user, key)  # Même tenant
    assert not can_view_translatable_key(regular_user, other_key)  # Tenant différent

# Tests pour can_change_translatable_key
def test_can_change_translatable_key(superuser, staff_user, regular_user):
    """Teste can_change_translatable_key avec multi-tenancy."""
    key = TranslatableKeyFactory.create(tenant_id="tenant_123")
    other_key = TranslatableKeyFactory.create(tenant_id="tenant_456")
    
    assert can_change_translatable_key(superuser, key)
    assert can_change_translatable_key(staff_user, key)
    assert can_change_translatable_key(regular_user, key)
    assert not can_change_translatable_key(regular_user, other_key)

# Tests pour can_view_translation
def test_can_view_translation(superuser, staff_user, regular_user):
    """Teste can_view_translation avec multi-tenancy."""
    translation = TranslationFactory.create(tenant_id="tenant_123")
    other_translation = TranslationFactory.create(tenant_id="tenant_456")
    
    assert can_view_translation(superuser, translation)
    assert can_view_translation(staff_user, translation)
    assert can_view_translation(regular_user, translation)
    assert not can_view_translation(regular_user, other_translation)

# Tests pour can_change_translation
def test_can_change_translation(superuser, staff_user, regular_user):
    """Teste can_change_translation avec langue choisie et multi-tenancy."""
    translation = TranslationFactory.create(tenant_id="tenant_123", language__code="fr")
    other_translation = TranslationFactory.create(tenant_id="tenant_456", language__code="fr")
    
    assert can_change_translation(superuser, translation, selected_language="fr")
    assert can_change_translation(staff_user, translation, selected_language="fr")
    assert can_change_translation(regular_user, translation, selected_language="fr")
    assert not can_change_translation(regular_user, other_translation, selected_language="fr")
    assert not can_change_translation(regular_user, translation, selected_language="en")  # Langue non correspondante

# Tests pour can_view_translation_job
def test_can_view_translation_job(superuser, staff_user, regular_user):
    """Teste can_view_translation_job pour admin/staff uniquement."""
    job = TranslationJobFactory.create()
    
    assert can_view_translation_job(superuser, job)
    assert can_view_translation_job(staff_user, job)
    assert not can_view_translation_job(regular_user, job)

# Tests pour can_rerun_translation_job
def test_can_rerun_translation_job(superuser, staff_user, regular_user):
    """Teste can_rerun_translation_job pour jobs non running."""
    job = TranslationJobFactory.create(state="done")
    running_job = TranslationJobFactory.create(state="running")
    
    assert can_rerun_translation_job(superuser, job)
    assert can_rerun_translation_job(staff_user, job)
    assert not can_rerun_translation_job(regular_user, job)
    assert not can_rerun_translation_job(superuser, running_job)  # Job running

# Tests pour can_export_translation_job
def test_can_export_translation_job(superuser, staff_user, regular_user):
    """Teste can_export_translation_job pour admin/staff."""
    job = TranslationJobFactory.create()
    
    assert can_export_translation_job(superuser, job)
    assert can_export_translation_job(staff_user, job)
    assert not can_export_translation_job(regular_user, job)

# Test pour tenant_id invalide
def test_invalid_tenant_id():
    """Teste validation tenant_id dans _get_obj_tenant_id."""
    key = TranslatableKeyFactory.create(tenant_id="invalid")
    with pytest.raises(ValidationError, match="Invalid tenant_id format"):
        can_view_translatable_key(User(), key)

# Test pour LANGUAGE_STAFF_GLOBAL
@override_settings(LANGUAGE_STAFF_GLOBAL=False)
def test_language_staff_global_false(staff_user, regular_user):
    """Teste comportement avec LANGUAGE_STAFF_GLOBAL=False."""
    key = TranslatableKeyFactory.create(tenant_id="tenant_123")
    staff_user.tenant_id = "tenant_456"
    staff_user.save()
    
    assert not can_view_translatable_key(staff_user, key)  # Tenant différent
    assert can_view_translatable_key(regular_user, key)  # Même tenant

