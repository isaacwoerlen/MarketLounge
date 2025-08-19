# tests/test_services.py
import pytest
import hashlib
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import override_settings
from transversales.language.services import (
    compute_checksum, validate_seo_lengths, get_active_language,
    safe_translate_text, tm_lookup, store_translation,
    batch_translate_items, batch_translate_scope
)
from transversales.language.models import Language, TranslatableKey, Translation
from transversales.language.utils import normalize_locale
from transversales.LLM_ai.services import LLMError

pytestmark = pytest.mark.django_db

@pytest.fixture
def language():
    """Fixture pour une langue active."""
    return Language.objects.create(
        code="fr",
        name="Français",
        is_active=True,
        is_default=True,
        priority=1
    )

@pytest.fixture
def translatable_key(language):
    """Fixture pour une clé traduisible."""
    return TranslatableKey.objects.create(
        scope="glossary",
        key="label",
        tenant_id="tenant_123"
    )

@pytest.fixture
def translation(translatable_key, language):
    """Fixture pour une traduction."""
    return Translation.objects.create(
        key=translatable_key,
        language=language,
        text="Étiquette",
        source_checksum=hashlib.sha256("Étiquette".encode()).hexdigest(),
        origin="human",
        tenant_id="tenant_123"
    )

def test_compute_checksum():
    """Teste le calcul du checksum SHA256."""
    text = "test text"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert compute_checksum(text) == expected
    assert compute_checksum("") == hashlib.sha256("".encode("utf-8")).hexdigest()

def test_validate_seo_lengths():
    """Teste la validation SEO pour longueurs et placeholders."""
    text = "A" * 161
    source_text = "{{name}} test"
    alerts = validate_seo_lengths(text, source_text, field="description")
    assert len(alerts) == 1
    assert alerts[0]["type"] == "seo_length"
    assert "Too long (161 chars)" in alerts[0]["message"]

    alerts = validate_seo_lengths("no placeholders", source_text, field="description")
    assert len(alerts) == 1
    assert alerts[0]["type"] == "placeholder_mismatch"
    assert "{{name}}" in alerts[0]["message"]

    alerts = validate_seo_lengths(["kw1", "kw2"], "keywords")
    assert len(alerts) == 0  # Moins de SEO_KEYWORDS_MAX

def test_get_active_language(language):
    """Teste la récupération d'une langue active."""
    lang = get_active_language("fr")
    assert lang.code == "fr"
    assert lang.is_active

    with pytest.raises(ValidationError, match="Language 'es' is inactive or not found"):
        get_active_language("es")

@patch("transversales.LLM_ai.services.translate_text")
def test_safe_translate_text_success(mock_translate, language):
    """Teste la traduction avec succès et retries."""
    mock_translate.return_value = "Label"
    result = safe_translate_text("Étiquette", "fr", "en", prompt_template={"tone": "neutral"})
    assert result == "Label"
    mock_translate.assert_called_once_with(
        "Étiquette", "fr", "en",
        prompt="Translate 'Étiquette' from fr to en with neutral tone, max 100 characters"
    )

@patch("transversales.LLM_ai.services.translate_text")
def test_safe_translate_text_fallback(mock_translate, language):
    """Teste le fallback LLM si Mistral échoue."""
    mock_translate.side_effect = [LLMError("Mistral failed"), "Label"]
    with override_settings(LLM_FALLBACK_PROVIDER="openai"):
        result = safe_translate_text("Étiquette", "fr", "en")
        assert result == "Label"
        assert mock_translate.call_count == 2
        assert mock_translate.call_args_list[1][0][3] == "openai"

@patch("transversales.LLM_ai.services.translate_text", side_effect=LLMError("Mistral failed"))
def test_safe_translate_text_failure(mock_translate, language):
    """Teste l'échec après retries sans fallback."""
    with override_settings(LLM_FALLBACK_PROVIDER=None):
        with pytest.raises(LLMError, match="Translation failed"):
            safe_translate_text("Étiquette", "fr", "en")
        assert mock_translate.call_count == 3  # 3 retries

def test_tm_lookup_hit(translatable_key, language):
    """Teste le cache hit pour Translation Memory."""
    cache_key = f"tm:{translatable_key.id}:checksum:en:tenant_123"
    cache.set(cache_key, "Label", timeout=3600)
    result = tm_lookup(translatable_key.id, "checksum", "en", "tenant_123")
    assert result == "Label"

def test_tm_lookup_miss(translatable_key):
    """Teste le cache miss pour Translation Memory."""
    result = tm_lookup(translatable_key.id, "checksum", "en", "tenant_123")
    assert result is None

def test_store_translation_idempotence(translatable_key, language, translation):
    """Teste l'idempotence de store_translation."""
    initial_count = Translation.objects.count()
    store_translation(
        key=translatable_key,
        target_lang="fr",
        translated_text="Étiquette",
        source_text="Étiquette",
        source_checksum=translation.source_checksum,
        origin="human",
        tenant_id="tenant_123"
    )
    assert Translation.objects.count() == initial_count  # Pas de nouvelle traduction

@patch("transversales.matching.services.encode_text")
def test_store_translation_vectorization(mock_encode, translatable_key, language):
    """Teste store_translation avec vectorisation sync."""
    mock_encode.return_value = [0.1] * 384
    with override_settings(LANG_EMBED_SYNC=True):
        store_translation(
            key=translatable_key,
            target_lang="fr",
            translated_text="Étiquette",
            source_text="Étiquette",
            source_checksum=hashlib.sha256("Étiquette".encode()).hexdigest(),
            origin="human",
            tenant_id="tenant_123"
        )
        translation = Translation.objects.get(key=translatable_key, language__code="fr")
        assert translation.embedding is not None
        mock_encode.assert_called_once_with("Étiquette")

@patch("transversales.LLM_ai.services.translate_text")
def test_batch_translate_items(mock_translate, translatable_key, language):
    """Teste batch_translate_items avec TM et LLM."""
    mock_translate.return_value = "Label"
    cache.set(f"tm:{translatable_key.id}:checksum:en:tenant_123", "Cached Label", timeout=3600)
    
    stats = batch_translate_items(
        item_ids=[str(translatable_key.id)],
        fields=["label"],
        source_lang="fr",
        target_langs=["en"],
        tenant_id="tenant_123"
    )
    assert stats["processed"] == 1
    assert stats["per_lang"]["en"] == 1
    assert stats["origin_breakdown"]["tm"] == 1
    assert not mock_translate.called  # TM hit

@patch("transversales.LLM_ai.services.translate_text")
def test_batch_translate_scope(mock_translate, translatable_key, language):
    """Teste batch_translate_scope avec LLM."""
    mock_translate.return_value = "Label"
    stats = batch_translate_scope(
        scope="glossary",
        source_lang="fr",
        target_langs=["en"],
        tenant_id="tenant_123"
    )
    assert stats["processed"] == 1
    assert stats["per_lang"]["en"] == 1
    assert stats["origin_breakdown"]["llm"] == 1
    mock_translate.assert_called_once()
    