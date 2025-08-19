# tests/test_tasks.py
import pytest
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone
from transversales.language.tasks import (
    run_batch_translation_items,
    run_batch_translation_scope,
    run_vectorize_scopes
)
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.utils import normalize_locale
from celery.exceptions import Retry
from transversales.LLM_ai.services import LLMError

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

# Tests pour run_batch_translation_items
@patch("transversales.language.tasks.batch_translate_items")
def test_run_batch_translation_items_success(mock_translate, language, translatable_key):
    """Teste run_batch_translation_items avec succès."""
    mock_translate.return_value = {
        "processed": 1,
        "skipped": 0,
        "per_lang": {"en": 1},
        "errors": [],
        "origin_breakdown": {"llm": 1}
    }
    job = TranslationJobFactory.create()
    result = run_batch_translation_items(
        item_ids=[str(translatable_key.id)],
        source_lang="fr",
        target_langs=["en"],
        fields=["label"],
        tenant_id="tenant_123"
    )
    assert result["processed"] == 1
    assert result["per_lang"]["en"] == 1
    job.refresh_from_db()
    assert job.state == "done"
    assert job.stats == result
    assert job.errors == []
    mock_translate.assert_called_once_with(
        item_ids=[str(translatable_key.id)],
        fields=["label"],
        source_lang="fr",
        target_langs=["en"],
        only_missing=True,
        include_seo=True,
        skip_if_target_exists=False,
        tenant_id="tenant_123"
    )

@patch("transversales.language.tasks.batch_translate_items")
def test_run_batch_translation_items_validation_error(mock_translate, language):
    """Teste run_batch_translation_items avec erreur de validation."""
    mock_translate.side_effect = ValidationError("Invalid input")
    job = TranslationJobFactory.create()
    with pytest.raises(ValidationError, match="Invalid input"):
        run_batch_translation_items(
            item_ids=["invalid"],
            source_lang="xyz",
            target_langs=["en"],
            tenant_id="tenant_123"
        )
    job.refresh_from_db()
    assert job.state == "failed"
    assert job.errors == ["Invalid input"]

@patch("transversales.language.tasks.batch_translate_items", side_effect=Exception("Unexpected error"))
def test_run_batch_translation_items_retry(mock_translate, language):
    """Teste run_batch_translation_items avec retry sur erreur inattendue."""
    job = TranslationJobFactory.create()
    with pytest.raises(Retry):
        run_batch_translation_items(
            item_ids=["1"],
            source_lang="fr",
            target_langs=["en"],
            tenant_id="tenant_123"
        )
    job.refresh_from_db()
    assert job.state == "failed"
    assert job.errors == ["Unexpected error"]

# Tests pour run_batch_translation_scope
@patch("transversales.language.tasks.batch_translate_scope")
def test_run_batch_translation_scope_success(mock_translate, language, translatable_key):
    """Teste run_batch_translation_scope avec succès."""
    mock_translate.return_value = {
        "processed": 1,
        "skipped": 0,
        "per_lang": {"en": 1},
        "errors": [],
        "origin_breakdown": {"llm": 1}
    }
    job = TranslationJobFactory.create(scope_filter=["glossary"])
    result = run_batch_translation_scope(
        scope="glossary",
        source_lang="fr",
        target_langs=["en"],
        tenant_id="tenant_123"
    )
    assert result["processed"] == 1
    assert result["per_lang"]["en"] == 1
    job.refresh_from_db()
    assert job.state == "done"
    assert job.stats == result
    assert job.errors == []
    mock_translate.assert_called_once_with(
        scope="glossary",
        source_lang="fr",
        target_langs=["en"],
        fields=None,
        tenant_id="tenant_123"
    )

@patch("transversales.language.tasks.batch_translate_scope")
def test_run_batch_translation_scope_validation_error(mock_translate, language):
    """Teste run_batch_translation_scope avec erreur de validation."""
    mock_translate.side_effect = ValidationError("Invalid scope")
    job = TranslationJobFactory.create(scope_filter=["invalid"])
    with pytest.raises(ValidationError, match="Invalid scope"):
        run_batch_translation_scope(
            scope="invalid",
            source_lang="fr",
            target_langs=["en"],
            tenant_id="tenant_123"
        )
    job.refresh_from_db()
    assert job.state == "failed"
    assert job.errors == ["Invalid scope"]

# Tests pour run_vectorize_scopes
@patch("transversales.language.tasks.encode_text")
def test_run_vectorize_scopes_success(mock_encode, translatable_key, language):
    """Teste run_vectorize_scopes avec succès."""
    translation = TranslationFactory.create(key=translatable_key, language=language, embedding=None)
    mock_encode.return_value = [0.1] * 384
    result = run_vectorize_scopes(scopes=["glossary"], tenant_id="tenant_123")
    assert result["vectorized"] == 1
    assert result["errors"] == 0
    translation.refresh_from_db()
    assert translation.embedding is not None
    mock_encode.assert_called_once_with(translation.text)

@patch("transversales.language.tasks.encode_text", side_effect=Exception("Encode error"))
def test_run_vectorize_scopes_failure(mock_encode, translatable_key, language):
    """Teste run_vectorize_scopes avec erreur encode_text."""
    translation = TranslationFactory.create(key=translatable_key, language=language, embedding=None)
    with pytest.raises(Retry):
        run_vectorize_scopes(scopes=["glossary"], tenant_id="tenant_123")
    translation.refresh_from_db()
    assert translation.embedding is None

def test_run_vectorize_scopes_sync_skip(language):
    """Teste run_vectorize_scopes avec LANG_EMBED_SYNC=True."""
    with override_settings(LANG_EMBED_SYNC=True):
        result = run_vectorize_scopes(scopes=["glossary"], tenant_id="tenant_123")
        assert result["vectorized"] == 0
        assert result["errors"] == 0

def test_run_vectorize_scopes_invalid_scopes():
    """Teste run_vectorize_scopes avec scopes invalides."""
    with pytest.raises(ValidationError, match="Scopes must be non-empty strings"):
        run_vectorize_scopes(scopes=[""])

