# tests/test_sync_translations.py
import pytest
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.test import override_settings
from io import StringIO
from transversales.language.models import Language, TranslatableKey, TranslationJob
from transversales.language.management.commands.sync_translations import Command
import json

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

# Tests pour Command
def test_sync_translations_no_args():
    """Teste l'erreur si ni scope ni item-ids fournis."""
    with pytest.raises(CommandError, match="Either --scope or --item-ids must be provided"):
        call_command("sync_translations")

def test_sync_translations_scope_and_items():
    """Teste l'erreur si scope et item-ids sont fournis ensemble."""
    with pytest.raises(CommandError, match="Cannot specify both --scope and --item-ids"):
        call_command("sync_translations", "--scope", "glossary", "--item-ids", "1")

def test_sync_translations_no_target_langs():
    """Teste l'erreur si aucune langue cible fournie."""
    with pytest.raises(CommandError, match="At least one target language must be provided"):
        call_command("sync_translations", "--scope", "glossary", "--target-langs", "")

@patch("transversales.language.tasks.run_batch_translation_items")
def test_sync_translations_items_async(mock_task):
    """Teste sync_translations avec item-ids en mode async."""
    LanguageFactory.create(code="en", is_default=False)
    key = TranslatableKeyFactory.create()
    mock_task.delay.return_value.id = "task-123"
    
    out = StringIO()
    call_command("sync_translations", "--item-ids", str(key.id), "--target-langs", "en", stdout=out)
    output = out.getvalue()
    assert "Sync completed" in output
    assert '"task_id": "task-123"' in output
    mock_task.delay.assert_called_once_with(
        item_ids=[str(key.id)],
        fields=["label", "definition"],
        source_lang="fr",
        target_langs=["en"],
        only_missing=True,
        include_seo=True,
        skip_if_target_exists=True,
        tenant_id=None
    )

@patch("transversales.language.services.batch_translate_items")
def test_sync_translations_items_sync(mock_service):
    """Teste sync_translations avec item-ids en mode sync."""
    LanguageFactory.create(code="en", is_default=False)
    key = TranslatableKeyFactory.create()
    mock_service.return_value = {
        "processed": 1,
        "skipped": 0,
        "per_lang": {"en": 1},
        "errors": [],
        "origin_breakdown": {"llm": 1}
    }
    
    out = StringIO()
    call_command("sync_translations", "--item-ids", str(key.id), "--target-langs", "en", "--sync", stdout=out)
    output = out.getvalue()
    assert "Sync completed" in output
    assert '"processed": 1' in output
    mock_service.assert_called_once_with(
        item_ids=[str(key.id)],
        fields=["label", "definition"],
        source_lang="fr",
        target_langs=["en"],
        only_missing=True,
        include_seo=True,
        skip_if_target_exists=True,
        tenant_id=None
    )

@patch("transversales.language.tasks.run_batch_translation_scope")
def test_sync_translations_scope_async(mock_task):
    """Teste sync_translations avec scope en mode async."""
    LanguageFactory.create(code="en", is_default=False)
    mock_task.delay.return_value.id = "task-456"
    
    out = StringIO()
    call_command("sync_translations", "--scope", "glossary", "--target-langs", "en", stdout=out)
    output = out.getvalue()
    assert "Sync completed" in output
    assert '"task_id": "task-456"' in output
    mock_task.delay.assert_called_once_with(
        scope="glossary",
        source_lang="fr",
        target_langs=["en"],
        fields=["label", "definition"],
        only_missing=True,
        include_seo=True,
        skip_if_target_exists=True,
        tenant_id=None
    )

@patch("transversales.language.services.batch_translate_scope")
def test_sync_translations_scope_sync(mock_service):
    """Teste sync_translations avec scope en mode sync."""
    LanguageFactory.create(code="en", is_default=False)
    mock_service.return_value = {
        "processed": 1,
        "skipped": 0,
        "per_lang": {"en": 1},
        "errors": [],
        "origin_breakdown": {"llm": 1}
    }
    
    out = StringIO()
    call_command("sync_translations", "--scope", "glossary", "--target-langs", "en", "--sync", stdout=out)
    output = out.getvalue()
    assert "Sync completed" in output
    assert '"processed": 1' in output
    mock_service.assert_called_once_with(
        scope="glossary",
        source_lang="fr",
        target_langs=["en"],
        fields=["label", "definition"],
        tenant_id=None
    )

def test_sync_translations_dry_run():
    """Teste sync_translations avec --dry-run."""
    key = TranslatableKeyFactory.create()
    out = StringIO()
    call_command("sync_translations", "--item-ids", str(key.id), "--dry-run", stdout=out)
    output = out.getvalue()
    assert "Estimated 1 translations" in output
    assert TranslationJob.objects.count() == 0  # Pas de job créé

def test_sync_translations_json_output():
    """Teste sync_translations avec --json."""
    key = TranslatableKeyFactory.create()
    out = StringIO()
    call_command("sync_translations", "--item-ids", str(key.id), "--dry-run", "--json", stdout=out)
    output = json.loads(out.getvalue())
    assert "estimated" in output
    assert output["details"]["items"] == 1
    assert output["details"]["target_langs"] == ["fr", "en"]

@patch("transversales.language.services.batch_translate_items", side_effect=TimeoutError("Timeout"))
def test_sync_translations_timeout(mock_service):
    """Teste sync_translations avec timeout en mode sync."""
    key = TranslatableKeyFactory.create()
    with pytest.raises(CommandError, match="Translation timed out"):
        call_command("sync_translations", "--item-ids", str(key.id), "--sync")
    assert mock_service.called
    