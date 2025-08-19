# tests/test_serializers.py
import pytest
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import override_settings
from transversales.language.serializers import (
    LanguageSerializer, TranslatableKeySerializer, TranslationSerializer,
    TranslationCreateSerializer, TranslationJobSerializer
)
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.utils import normalize_locale

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
            "alerts": [{"type": "seo_length", "field": "text", "message": "Too long"}],
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

# Tests pour LanguageSerializer
def test_language_serializer():
    """Teste la sérialisation de Language."""
    language = LanguageFactory.create(code="en", is_default=False)
    serializer = LanguageSerializer(language)
    data = serializer.data
    assert data["code"] == "en"
    assert data["name"] == "English"
    assert data["is_active"] is True
    assert data["is_default"] is False
    assert "created_at" in data

# Tests pour TranslatableKeySerializer
def test_translatable_key_serializer_validation():
    """Teste la validation de TranslatableKeySerializer (unicité, prompt_template)."""
    TranslatableKeyFactory.create(scope="seo", key="title", tenant_id="tenant_123")
    data = {
        "scope": "seo",
        "key": "title",
        "tenant_id": "tenant_123",
        "prompt_template": {"tone": "neutral"}
    }
    serializer = TranslatableKeySerializer(data=data)
    assert not serializer.is_valid()
    assert "A key with this scope and tenant already exists" in str(serializer.errors)

    # prompt_template invalide
    data["prompt_template"] = ["invalid"]
    serializer = TranslatableKeySerializer(data=data)
    assert not serializer.is_valid()
    assert "prompt_template must be a dictionary" in str(serializer.errors)

def test_translatable_key_serializer_create():
    """Teste la création avec TranslatableKeySerializer."""
    data = {
        "scope": "glossary",
        "key": "description",
        "tenant_id": "tenant_456",
        "prompt_template": {"tone": "formal", "max_length": 60}
    }
    serializer = TranslatableKeySerializer(data=data)
    assert serializer.is_valid()
    key = serializer.save()
    assert key.scope == "glossary"
    assert key.tenant_id == "tenant_456"
    assert key.prompt_template == {"tone": "formal", "max_length": 60}

# Tests pour TranslationSerializer
def test_translation_serializer_nested():
    """Teste la sérialisation nested de TranslationSerializer (depth=1)."""
    translation = TranslationFactory.create()
    serializer = TranslationSerializer(translation)
    data = serializer.data
    assert data["key_scope"] == "glossary"
    assert data["key_name"] == "label"
    assert data["language_code"] == "fr"
    assert data["text"] == "Étiquette"
    assert data["has_embedding"] is False
    assert data["alerts"] == [{"type": "seo_length", "field": "text", "message": "Too long"}]

def test_translation_serializer_alerts_validation():
    """Teste la validation JSON de alerts dans TranslationSerializer."""
    translation = TranslationFactory.create(alerts=[{"type": "seo_length"}])
    serializer = TranslationSerializer(translation, data={"alerts": [{"type": "seo_length"}]})
    assert not serializer.is_valid()
    assert "alerts must be a list of dictionaries with type, field, message" in str(serializer.errors)

# Tests pour TranslationCreateSerializer
@patch("transversales.language.services.store_translation")
def test_translation_create_serializer(mock_store):
    """Teste la création avec TranslationCreateSerializer."""
    key = TranslatableKeyFactory.create()
    data = {
        "key": key.id,
        "target_lang": "en",
        "translated_text": "Label",
        "source_text": "Étiquette",
    }
    serializer = TranslationCreateSerializer(data=data, context={"alerts": [{"type": "seo_length", "field": "text", "message": "Too long"}]})
    assert serializer.is_valid()
    translation = serializer.save()
    mock_store.assert_called_once_with(
        key=key,
        target_lang="en",
        translated_text="Label",
        source_text="Étiquette",
        source_checksum=mock_store.call_args[1]["source_checksum"],
        origin="human",
        field="text",
        tenant_id=key.tenant_id,
        alerts=[{"type": "seo_length", "field": "text", "message": "Too long"}]
    )
    assert translation.text == "Label"

def test_translation_create_serializer_invalid_alerts():
    """Teste la validation JSON de alerts dans TranslationCreateSerializer."""
    key = TranslatableKeyFactory.create()
    data = {
        "key": key.id,
        "target_lang": "en",
        "translated_text": "Label",
        "source_text": "Étiquette",
    }
    serializer = TranslationCreateSerializer(data=data, context={"alerts": [{"type": "seo_length"}]})
    assert not serializer.is_valid()
    assert "alerts must be a list of dictionaries with type, field, message" in str(serializer.errors)

# Tests pour TranslationJobSerializer
def test_translation_job_serializer_validation():
    """Teste la validation de TranslationJobSerializer (source_locale, target_locales, JSON)."""
    data = {
        "name": "Test Job",
        "source_locale": "fr",
        "target_locales": ["fr", "en"],
        "scope_filter": ["glossary"],
        "tenant_id": "tenant_123",
        "stats": ["invalid"],
    }
    serializer = TranslationJobSerializer(data=data)
    assert not serializer.is_valid()
    assert "stats must be a dictionary" in str(serializer.errors)

    data["stats"] = {"processed": 0}
    data["target_locales"] = ["fr"]  # Source dans target
    serializer = TranslationJobSerializer(data=data)
    assert not serializer.is_valid()
    assert "Source locale fr cannot be in target locales" in str(serializer.errors)

def test_translation_job_serializer_create():
    """Teste la création avec TranslationJobSerializer."""
    LanguageFactory.create(code="en", is_default=False)
    data = {
        "name": "Test Job",
        "source_locale": "fr",
        "target_locales": ["en"],
        "scope_filter": ["glossary"],
        "tenant_id": "tenant_123",
    }
    serializer = TranslationJobSerializer(data=data)
    assert serializer.is_valid()
    job = serializer.save()
    assert job.source_locale == "fr"
    assert job.target_locales == ["en"]
    assert job.state == "queued"
