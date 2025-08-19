# tests/test_models.py
import pytest
import hashlib
import numpy as np
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import override_settings
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.utils import normalize_locale

pytestmark = pytest.mark.django_db

# Factories pour générer des données de test
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
            "source_checksum": hashlib.sha256("Étiquette".encode()).hexdigest(),
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

# Tests pour Language
def test_language_validation():
    """Teste les validations de Language (code, is_default, is_active)."""
    # Code valide
    lang = LanguageFactory.create(code="pt-br", is_default=False)
    assert lang.code == "pt-br"
    assert normalize_locale(lang.code) == lang.code

    # Code invalide
    with pytest.raises(ValidationError, match="Invalid language code"):
        LanguageFactory.create(code="xyz")

    # is_default implique is_active
    with pytest.raises(ValidationError, match="Default language must be active"):
        LanguageFactory.create(is_default=True, is_active=False)

    # Unicité is_default
    LanguageFactory.create(code="en", is_default=True)
    with pytest.raises(ValidationError, match="Only one default language"):
        LanguageFactory.create(code="es", is_default=True)

def test_language_manager_get_default():
    """Teste LanguageManager.get_default avec cache."""
    LanguageFactory.create(code="fr", is_default=True)
    with override_settings(LANG_CACHE_TTL=300):
        result = Language.objects.get_default()
        assert result == "fr"
        assert cache.get("language:default") == "fr"

def test_language_manager_get_active():
    """Teste LanguageManager.get_active avec cache."""
    LanguageFactory.create(code="fr", priority=1)
    LanguageFactory.create(code="en", priority=2)
    with override_settings(LANG_CACHE_TTL=300):
        result = Language.objects.get_active()
        assert result == ["fr", "en"]
        assert cache.get("language:active") == ["fr", "en"]

# Tests pour TranslatableKey
def test_translatable_key_validation():
    """Teste les validations de TranslatableKey (scope, key, tenant_id, prompt_template)."""
    # Clé valide
    key = TranslatableKeyFactory.create(scope="seo", key="title", tenant_id="tenant_456")
    assert key.checksum == hashlib.sha256("seo:title".encode()).hexdigest()

    # Unicité scope+key+tenant_id
    with pytest.raises(ValidationError, match="A key with this scope and tenant"):
        TranslatableKeyFactory.create(scope="seo", key="title", tenant_id="tenant_456")

    # prompt_template JSON
    with pytest.raises(ValidationError, match="prompt_template must be a dictionary"):
        TranslatableKeyFactory.create(prompt_template=["invalid"])

    # tenant_id invalide
    with pytest.raises(ValidationError, match="Invalid tenant_id format"):
        TranslatableKeyFactory.create(tenant_id="invalid")

# Tests pour Translation
def test_translation_validation():
    """Teste les validations de Translation (text, tenant_id, alerts, embedding)."""
    key = TranslatableKeyFactory.create()
    lang = LanguageFactory.create()

    # Traduction valide
    translation = TranslationFactory.create(key=key, language=lang)
    assert translation.source_checksum == hashlib.sha256("Étiquette".encode()).hexdigest()

    # Text requis sauf origin=human
    with pytest.raises(ValidationError, match="Text is required"):
        TranslationFactory.create(text="", origin="llm")

    # Tenant mismatch
    with pytest.raises(ValidationError, match="Tenant ID must match"):
        TranslationFactory.create(key=key, tenant_id="tenant_999")

    # Alerts JSON
    with pytest.raises(ValidationError, match="alerts must be a list of dictionaries"):
        TranslationFactory.create(alerts=[{"type": "seo_length"}])

def test_translation_embedding_normalization():
    """Teste la normalisation L2 de Translation.embedding."""
    key = TranslatableKeyFactory.create()
    lang = LanguageFactory.create()
    embedding = [1.0, 0.0] * 192  # dim=384
    norm = np.linalg.norm(embedding)
    translation = TranslationFactory.create(key=key, language=lang, embedding=embedding)
    assert np.allclose(np.linalg.norm(translation.embedding), 1.0)  # Normalisé L2
    # Embedding zéro
    translation = TranslationFactory.create(key=key, language=lang, embedding=[0.0] * 384)
    assert translation.embedding is None

# Tests pour TranslationJob
def test_translation_job_validation():
    """Teste les validations de TranslationJob (source_locale, target_locales, stats, errors)."""
    job = TranslationJobFactory.create(source_locale="fr", target_locales=["en", "pt-br"])
    assert job.source_locale == "fr"
    assert job.target_locales == ["en", "pt-br"]

    # Source_locale invalide
    with pytest.raises(ValidationError, match="Invalid language code"):
        TranslationJobFactory.create(source_locale="xyz")

    # target_locales JSON
    with pytest.raises(ValidationError, match="target_locales must be a list"):
        TranslationJobFactory.create(target_locales="invalid")

    # stats JSON
    with pytest.raises(ValidationError, match="stats must be a dictionary"):
        TranslationJobFactory.create(stats=["invalid"])

    # errors JSON
    with pytest.raises(ValidationError, match="errors must be a list"):
        TranslationJobFactory.create(errors={"invalid": "error"})

def test_translation_job_get_default_lang():
    """Teste TranslationJob.get_default_lang."""
    LanguageFactory.create(code="fr", is_default=True)
    lang = TranslationJob.get_default_lang()
    assert lang.code == "fr"

    # Fallback si aucune langue
    Language.objects.all().delete()
    lang = TranslationJob.get_default_lang()
    assert lang.code == "fr"

