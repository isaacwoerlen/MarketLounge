# tests/test_apps.py
import pytest
from unittest.mock import patch
from django.test import override_settings
from django.core.checks import Warning
from django.db import DatabaseError
from transversales.language.apps import LanguageConfig, language_checks, seed_default_langs
from transversales.language.models import Language
from django.core.cache import cache

pytestmark = pytest.mark.django_db

# Factory pour données de test
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

# Tests pour language_checks
def test_language_checks_no_active_language():
    """Teste le check W001 : aucune langue active."""
    with override_settings(LANG_CHECKS_DISABLE=False):
        issues = language_checks(None)
        assert len(issues) == 2  # W001 (no active) + W002 (no default)
        assert any(issue.id == "language.W001" for issue in issues)
        assert any(issue.id == "language.W002" for issue in issues)

def test_language_checks_no_default_language():
    """Teste le check W002 : aucune langue par défaut."""
    LanguageFactory.create(is_default=False)
    with override_settings(LANG_CHECKS_DISABLE=False):
        issues = language_checks(None)
        assert len(issues) == 1
        assert issues[0].id == "language.W002"

def test_language_checks_multiple_default_languages():
    """Teste le check W003 : plusieurs langues par défaut."""
    LanguageFactory.create(code="fr", is_default=True)
    LanguageFactory.create(code="en", is_default=True)
    with override_settings(LANG_CHECKS_DISABLE=False):
        issues = language_checks(None)
        assert len(issues) == 1
        assert issues[0].id == "language.W003"

def test_language_checks_default_inactive():
    """Teste le check W004 : langue par défaut inactive."""
    LanguageFactory.create(is_default=True, is_active=False)
    with override_settings(LANG_CHECKS_DISABLE=False):
        issues = language_checks(None)
        assert len(issues) == 1
        assert issues[0].id == "language.W004"

def test_language_checks_database_error():
    """Teste le check W005 : erreur base de données."""
    with patch("transversales.language.models.Language.objects.filter", side_effect=DatabaseError("DB error")):
        with override_settings(LANG_CHECKS_DISABLE=False):
            issues = language_checks(None)
            assert len(issues) == 1
            assert issues[0].id == "language.W005"

def test_language_checks_disabled():
    """Teste désactivation des checks via LANG_CHECKS_DISABLE."""
    with override_settings(LANG_CHECKS_DISABLE=True):
        issues = language_checks(None)
        assert len(issues) == 0

def test_language_checks_success():
    """Teste succès des checks avec configuration valide."""
    LanguageFactory.create(code="fr", is_default=True)
    with override_settings(LANG_CHECKS_DISABLE=False):
        issues = language_checks(None)
        assert len(issues) == 0

# Tests pour seed_default_langs
@patch("transversales.language.utils.clear_lang_caches")
def test_seed_default_langs_empty_table(mock_clear):
    """Teste seeding avec table vide."""
    with override_settings(DEFAULT_LANG="fr", ACTIVE_LANGS=["fr", "en"]):
        seed_default_langs(None)
        assert Language.objects.count() == 2
        assert Language.objects.filter(code="fr", is_default=True, is_active=True).exists()
        assert Language.objects.filter(code="en", is_default=False, is_active=True).exists()
        mock_clear.assert_called_once()

def test_seed_default_langs_idempotent():
    """Teste idempotence du seeding."""
    LanguageFactory.create(code="fr", is_default=True)
    initial_count = Language.objects.count()
    with override_settings(DEFAULT_LANG="fr", ACTIVE_LANGS=["fr", "en"]):
        seed_default_langs(None)
        assert Language.objects.count() == initial_count  # Pas de nouvelles langues

def test_seed_default_langs_invalid_code():
    """Teste seeding avec code langue invalide."""
    with override_settings(DEFAULT_LANG="xyz", ACTIVE_LANGS=["xyz"]):
        with pytest.raises(Exception, match="Invalid language code"):
            seed_default_langs(None)
        assert Language.objects.count() == 0

def test_seed_default_langs_disabled():
    """Teste désactivation du seeding via LANG_SEED_DISABLE."""
    with override_settings(LANG_SEED_DISABLE=True):
        seed_default_langs(None)
        assert Language.objects.count() == 0

@patch("transversales.language.models.Language.objects.get_or_create", side_effect=DatabaseError("DB error"))
def test_seed_default_langs_database_error(mock_get_or_create):
    """Teste seeding avec erreur base de données."""
    with override_settings(DEFAULT_LANG="fr", ACTIVE_LANGS=["fr", "en"]):
        with pytest.raises(DatabaseError):
            seed_default_langs(None)
        assert Language.objects.count() == 0

# Tests pour métriques
def test_language_checks_metrics():
    """Teste les métriques pour checks réussis et échoués."""
    with patch("transversales.metrics.services.record_metric") as mock_metric:
        LanguageFactory.create()
        with override_settings(LANG_CHECKS_DISABLE=False):
            language_checks(None)
            mock_metric.assert_any_call(
                name="language.check_success",
                value=1,
                tags={"description": "all_checks_passed"}
            )

    with patch("transversales.metrics.services.record_metric") as mock_metric:
        with override_settings(LANG_CHECKS_DISABLE=False):
            language_checks(None)
            mock_metric.assert_any_call(
                name="language.check_failed",
                value=1,
                tags={"check": "W001", "description": "no_active_language"}
            )

def test_seed_default_langs_metrics():
    """Teste les métriques pour seeding."""
    with patch("transversales.metrics.services.record_metric") as mock_metric:
        with override_settings(DEFAULT_LANG="fr", ACTIVE_LANGS=["fr", "en"]):
            seed_default_langs(None)
            mock_metric.assert_any_call(
                name="language.seed_success",
                value=1,
                tags={"code": "fr", "type": "default"}
            )
            mock_metric.assert_any_call(
                name="language.seed_success",
                value=1,
                tags={"code": "en", "type": "active"}
            )
