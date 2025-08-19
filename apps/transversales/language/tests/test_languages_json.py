# tests/test_languages_json.py
import pytest
import json
import os
from django.core.management import call_command, CommandError
from django.test import override_settings
from django.core.exceptions import ValidationError
from transversales.language.models import Language, TranslatableKey
from io import StringIO

pytestmark = pytest.mark.django_db

# Chemin vers languages.json
FIXTURE_PATH = "transversales/language/specific/fixtures/languages.json"

# Tests pour validité JSON
def test_languages_json_format():
    """Teste que languages.json est un JSON valide."""
    assert os.path.exists(FIXTURE_PATH), f"Fixture file {FIXTURE_PATH} not found"
    with open(FIXTURE_PATH, 'r') as f:
        data = json.load(f)
    assert isinstance(data, list), "languages.json must be a list"
    assert len(data) == 6, "Expected 6 fixtures (4 Language, 2 TranslatableKey)"
    for item in data:
        assert "model" in item, "Each fixture must have a model"
        assert "pk" in item, "Each fixture must have a pk"
        assert "fields" in item, "Each fixture must have fields"

# Tests pour chargement via loaddata
def test_languages_json_loaddata():
    """Teste le chargement correct de languages.json via loaddata."""
    out = StringIO()
    call_command("loaddata", FIXTURE_PATH, stdout=out)
    
    # Vérifier langues
    assert Language.objects.count() == 4, "Expected 4 languages"
    assert Language.objects.filter(code="fr", is_default=True, is_active=True).exists()
    assert Language.objects.filter(code="en", is_active=True).exists()
    assert Language.objects.filter(code="pt-br", is_active=True).exists()
    assert Language.objects.filter(code="es", is_active=False).exists()
    
    # Vérifier clés traduisibles
    assert TranslatableKey.objects.count() == 2, "Expected 2 translatable keys"
    assert TranslatableKey.objects.filter(scope="glossary", key="label", tenant_id="tenant_123").exists()
    assert TranslatableKey.objects.filter(scope="seo", key="title", tenant_id="tenant_456").exists()

# Tests pour conformité des données
def test_languages_json_data_validation():
    """Teste que les données de languages.json respectent les contraintes des modèles."""
    with open(FIXTURE_PATH, 'r') as f:
        data = json.load(f)
    
    for item in data:
        if item["model"] == "language.language":
            fields = item["fields"]
            assert re.match(r'^[a-z]{2}(-[a-z]{2})?$', fields["code"]), f"Invalid code: {fields['code']}"
            assert isinstance(fields["is_active"], bool), f"Invalid is_active: {fields['is_active']}"
            assert isinstance(fields["is_default"], bool), f"Invalid is_default: {fields['is_default']}"
        elif item["model"] == "language.translatablekey":
            fields = item["fields"]
            assert fields["tenant_id"].startswith("tenant_"), f"Invalid tenant_id: {fields['tenant_id']}"
            assert isinstance(fields["prompt_template"], dict), f"Invalid prompt_template: {fields['prompt_template']}"

# Tests pour JSON malformé
def test_languages_json_invalid_format(tmp_path):
    """Teste l'échec de loaddata avec JSON malformé."""
    invalid_json = tmp_path / "invalid_languages.json"
    invalid_json.write_text('[{"model": "language.language", "pk": 1, "fields": {"code": "fr"')  # JSON incomplet
    
    with pytest.raises(CommandError):
        call_command("loaddata", str(invalid_json))

# Tests pour données non conformes
def test_languages_json_invalid_data(tmp_path):
    """Teste l'échec de loaddata avec données non conformes."""
    invalid_data = [
        {"model": "language.language", "pk": 1, "fields": {"code": "xyz", "name": "Invalid", "is_active": True, "is_default": True}},
        {"model": "language.translatablekey", "pk": 1, "fields": {"scope": "glossary", "key": "label", "tenant_id": "invalid"}}
    ]
    invalid_json = tmp_path / "invalid_languages.json"
    invalid_json.write_text(json.dumps(invalid_data))
    
    with pytest.raises(CommandError):
        call_command("loaddata", str(invalid_json))

# Tests pour idempotence
def test_languages_json_idempotent():
    """Teste que loaddata est idempotent."""
    call_command("loaddata", FIXTURE_PATH)
    initial_count = Language.objects.count()
    initial_key_count = TranslatableKey.objects.count()
    
    call_command("loaddata", FIXTURE_PATH)
    assert Language.objects.count() == initial_count, "Language count should not change"
    assert TranslatableKey.objects.count() == initial_key_count, "TranslatableKey count should not change"

# Tests pour multi-tenancy
def test_languages_json_multi_tenancy():
    """Teste l'isolation multi-tenant dans languages.json."""
    call_command("loaddata", FIXTURE_PATH)
    key1 = TranslatableKey.objects.get(tenant_id="tenant_123")
    key2 = TranslatableKey.objects.get(tenant_id="tenant_456")
    assert key1.scope == "glossary"
    assert key2.scope == "seo"
    assert key1.tenant_id != key2.tenant_id
    