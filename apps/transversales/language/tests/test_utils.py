# tests/test_utils.py
import pytest
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import override_settings
from transversales.language.utils import (
    normalize_locale, _dedupe_and_normalize, _fallback_active, _fallback_default,
    get_active_langs, get_default_lang, clear_lang_caches, update_translations, seo_alerts
)
from transversales.language.models import Language, TranslatableKey, Translation
import hashlib

pytestmark = pytest.mark.django_db

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

# Tests pour normalize_locale
def test_normalize_locale():
    """Teste la normalisation des codes langues."""
    assert normalize_locale("PT_BR") == "pt-br"
    assert normalize_locale("fr") == "fr"
    assert normalize_locale("  EN  ") == "en"
    assert normalize_locale("xyz") == ""
    assert normalize_locale("") == ""

# Tests pour _dedupe_and_normalize
def test_dedupe_and_normalize():
    """Teste la déduplication et normalisation des codes langues."""
    codes = ["FR", "en", "PT-BR", "fr"]
    result = _dedupe_and_normalize(codes)
    assert result == ["fr", "en", "pt-br"]
    assert _dedupe_and_normalize([]) == []
    assert _dedupe_and_normalize(["xyz"]) == []

# Tests pour _fallback_active
def test_fallback_active():
    """Teste le fallback pour langues actives."""
    with override_settings(ACTIVE_LANGS=["fr", "EN", "pt_br"]):
        result = _fallback_active()
        assert result == ["fr", "en", "pt-br"]
    with override_settings(ACTIVE_LANGS=[]):
        result = _fallback_active()
        assert result == ["fr", "en"]

# Tests pour _fallback_default
def test_fallback_default():
    """Teste le fallback pour langue par défaut."""
    with override_settings(DEFAULT_LANG="PT-BR"):
        assert _fallback_default() == "pt-br"
    with override_settings(DEFAULT_LANG="xyz"):
        assert _fallback_default() == "fr"

# Tests pour get_active_langs
@patch("transversales.language.models.LanguageManager.get_active")
def test_get_active_langs(mock_get_active):
    """Teste get_active_langs avec cache et fallback."""
    LanguageFactory.create(code="fr")
    LanguageFactory.create(code="en")
    mock_get_active.return_value = ["fr", "en"]
    
    with override_settings(LANG_CACHE_TTL=300):
        result = get_active_langs()
        assert result == ["fr", "en"]
        assert cache.get("language:active") == ["fr", "en"]
    
    mock_get_active.side_effect = Exception("DB error")
    with override_settings(ACTIVE_LANGS=["es"]):
        result = get_active_langs()
        assert result == ["es"]

# Tests pour get_default_lang
@patch("transversales.language.models.LanguageManager.get_default")
def test_get_default_lang(mock_get_default):
    """Teste get_default_lang avec cache et fallback."""
    LanguageFactory.create(code="fr", is_default=True)
    mock_get_default.return_value = "fr"
    
    with override_settings(LANG_CACHE_TTL=300):
        result = get_default_lang()
        assert result == "fr"
        assert cache.get("language:default") == "fr"
    
    mock_get_default.side_effect = Exception("DB error")
    with override_settings(DEFAULT_LANG="en"):
        result = get_default_lang()
        assert result == "en"

# Tests pour clear_lang_caches
def test_clear_lang_caches():
    """Teste clear_lang_caches."""
    cache.set("language:active", ["fr", "en"])
    cache.set("language:default", "fr")
    clear_lang_caches()
    assert cache.get("language:active") is None
    assert cache.get("language:default") is None

# Tests pour update_translations
def test_update_translations():
    """Teste update_translations pour créer/mettre à jour clés et traductions."""
    language = LanguageFactory.create()
    model_instance = type("Model", (), {"label": "Étiquette"})()
    
    result = update_translations(model_instance, "glossary", ["label"], tenant_id="tenant_123")
    assert result == model_instance
    assert TranslatableKey.objects.count() == 1
    assert Translation.objects.count() == 1
    
    key = TranslatableKey.objects.get(scope="glossary", key="label")
    translation = Translation.objects.get(key=key, language=language)
    assert translation.text == "Étiquette"
    assert translation.tenant_id == "tenant_123"

def test_update_translations_idempotence():
    """Teste l'idempotence de update_translations."""
    language = LanguageFactory.create()
    TranslationFactory.create(text="Étiquette")
    
    initial_count = Translation.objects.count()
    model_instance = type("Model", (), {"label": "Étiquette"})()
    update_translations(model_instance, "glossary", ["label"], tenant_id="tenant_123")
    assert Translation.objects.count() == initial_count

def test_update_translations_error():
    """Teste update_translations avec erreur."""
    model_instance = type("Model", (), {"label": "Étiquette"})()
    with pytest.raises(Exception, match="DB error"):
        with patch("transversales.language.models.TranslatableKey.objects.get_or_create", side_effect=Exception("DB error")):
            update_translations(model_instance, "glossary", ["label"], tenant_id="tenant_123")

# Tests pour seo_alerts
def test_seo_alerts():
    """Teste seo_alerts pour title, description, keywords."""
    with override_settings(SEO_TITLE_MAX=60, SEO_DESC_MAX=160, SEO_KEYWORDS_MAX=10):
        # Title trop long
        alerts = seo_alerts("A" * 61, "title")
        assert len(alerts) == 1
        assert alerts[0]["type"] == "seo_length"
        assert "Titre trop long" in alerts[0]["message"]

        # Description OK
        alerts = seo_alerts("A" * 100, "description")
        assert len(alerts) == 0

        # Keywords trop nombreux
        alerts = seo_alerts(["kw" + str(i) for i in range(11)], "keywords")
        assert len(alerts) == 1
        assert "Trop de mots-clés" in alerts[0]["message"]

        # Keywords format invalide
        alerts = seo_alerts(123, "keywords")
        assert len(alerts) == 1
        assert "Format invalide" in alerts[0]["message"]
        