# tests/test_integration.py
import pytest
from unittest.mock import patch
from django.test import Client
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import override_settings
from io import StringIO
import json
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
from transversales.language.tests.factories import LanguageFactory, TranslatableKeyFactory, TranslationFactory, TranslationJobFactory
from transversales.LLM_ai.services import LLMError

pytestmark = pytest.mark.django_db

User = get_user_model()

@pytest.fixture
def superuser():
    return User.objects.create_superuser(username="admin", email="admin@example.com", password="admin123")

@pytest.fixture
def regular_user():
    return User.objects.create_user(username="user", email="user@example.com", password="user123", tenant_id="tenant_123")

@pytest.fixture
def client():
    return Client()

# Test flux complet : seeding → traduction → vectorisation → API
@patch("transversales.language.tasks.run_batch_translation_items")
@patch("transversales.language.tasks.run_vectorize_scopes")
@patch("transversales.LLM_ai.services.translate_text")
@patch("transversales.matching.services.encode_text")
def test_full_workflow_items(mock_encode, mock_translate, mock_vectorize, mock_translate_items, superuser, client):
    """Teste le flux complet : seeding, traduction, vectorisation, récupération API."""
    # 1. Seeding via loaddata
    call_command("loaddata", "transversales/language/specific/fixtures/languages.json")
    assert Language.objects.count() == 4
    assert TranslatableKey.objects.count() == 2

    # 2. Traduction via CLI (async)
    key = TranslatableKey.objects.get(scope="glossary", key="label")
    mock_translate.return_value = "Label"
    mock_translate_items.delay.return_value.id = "task-123"
    out = StringIO()
    call_command("sync_translations", "--item-ids", str(key.id), "--target-langs", "en", stdout=out)
    assert "task_id" in out.getvalue()
    mock_translate_items.delay.assert_called_once()

    # 3. Vectorisation via API
    job = TranslationJobFactory.create(tenant_id="tenant_123")
    mock_vectorize.delay.return_value.id = "vectorize-123"
    mock_encode.return_value = list([0.1] * 384)
    with override_settings(LANG_ENABLE_API=True):
        client.force_login(superuser)
        url = reverse("language:job-vectorize", kwargs={"pk": job.id})
        response = client.post(url)
        assert response.status_code == 200
        mock_vectorize.delay.assert_called_once()

    # 4. Récupération via API
    translation = TranslationFactory.create(key=key, language__code="en", tenant_id="tenant_123")
    url = reverse("language:translation-list")
    response = client.get(url)
    assert response.status_code == 200
    assert any(t["key_name"] == "label" for t in response.json())

# Test flux admin : création clé → traduction → export
@patch("transversales.language.tasks.run_batch_translation_items")
def test_admin_workflow(mock_translate_items, superuser, client):
    """Teste le flux admin : création clé, traduction, export CSV."""
    # 1. Création TranslatableKey via admin
    client.force_login(superuser)
    url = reverse("admin:language_translatablekey_add")
    response = client.post(url, {
        "scope": "seo",
        "key": "title",
        "tenant_id": "tenant_123",
        "prompt_template": json.dumps({"tone": "formal"}),
        "_save": "Save"
    }, follow=True)
    assert response.status_code == 200
    assert TranslatableKey.objects.filter(scope="seo", key="title").exists()

    # 2. Traduction via admin (rerun_job)
    key = TranslatableKey.objects.get(scope="seo", key="title")
    job = TranslationJobFactory.create(glossary_ids=[str(key.id)], tenant_id="tenant_123")
    mock_translate_items.delay.return_value.id = "task-123"
    url = reverse("admin:language_translationjob_rerun", kwargs={"object_id": job.id})
    response = client.post(url, follow=True)
    assert response.status_code == 200
    mock_translate_items.delay.assert_called_once()

    # 3. Export CSV via admin
    job.stats = {"per_lang": {"en": 5}}
    job.save()
    url = reverse("admin:language_translationjob_export", kwargs={"object_id": job.id})
    response = client.post(url)
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]

# Test multi-tenancy
def test_multi_tenancy_workflow(superuser, regular_user, client):
    """Teste l'isolation multi-tenant dans API et admin."""
    # Créer clés pour différents tenants
    key1 = TranslatableKeyFactory.create(tenant_id="tenant_123")
    key2 = TranslatableKeyFactory.create(tenant_id="tenant_456")
    
    # API : regular_user voit seulement son tenant
    with override_settings(LANG_ENABLE_API=True):
        client.force_login(regular_user)
        url = reverse("language:key-list")
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["tenant_id"] == "tenant_123"

    # Admin : superuser voit tous les tenants
    client.force_login(superuser)
    url = reverse("admin:language_translatablekey_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert "tenant_123" in response.content.decode()
    assert "tenant_456" in response.content.decode()

# Test erreur : LLM failure
@patch("transversales.LLM_ai.services.translate_text", side_effect=LLMError("LLM failed"))
def test_workflow_llm_failure(mock_translate, superuser):
    """Teste gestion erreur LLM dans traduction."""
    key = TranslatableKeyFactory.create()
    job = TranslationJobFactory.create(glossary_ids=[str(key.id)])
    out = StringIO()
    with pytest.raises(CommandError, match="Translation failed"):
        call_command("sync_translations", "--item-ids", str(key.id), "--sync", stdout=out)
    job.refresh_from_db()
    assert job.state == "failed"
    assert "LLM failed" in job.errors

# Test erreur : timeout
@patch("transversales.language.services.batch_translate_items", side_effect=TimeoutError("Timeout"))
def test_workflow_timeout(mock_service, superuser):
    """Teste gestion timeout dans traduction sync."""
    key = TranslatableKeyFactory.create()
    with pytest.raises(CommandError, match="Translation timed out"):
        call_command("sync_translations", "--item-ids", str(key.id), "--sync")

# Test scalabilité : batching
@patch("transversales.language.tasks.run_batch_translation_items")
def test_workflow_batching(mock_translate_items, superuser):
    """Teste batching pour multiples clés."""
    keys = [TranslatableKeyFactory.create() for _ in range(100)]
    item_ids = [str(key.id) for key in keys]
    mock_translate_items.delay.return_value.id = "task-123"
    out = StringIO()
    call_command("sync_translations", "--item-ids", ",".join(item_ids), "--target-langs", "en", stdout=out)
    assert "task_id" in out.getvalue()
    mock_translate_items.delay.assert_called_once_with(
        item_ids=item_ids,
        fields=["label", "definition"],
        source_lang="fr",
        target_langs=["en"],
        only_missing=True,
        include_seo=True,
        skip_if_target_exists=True,
        tenant_id=None
    )
    