# apps/transversales/language/apps.py
import logging
from django.apps import AppConfig
from django.conf import settings
from django.core.checks import register, Warning, Tags
from django.db.models.signals import post_migrate
from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from transversales.metrics.services import record_metric

logger = logging.getLogger(__name__)

# Validation regex pour codes langues
CODE_VALIDATOR = RegexValidator(
    regex=r'^[a-z]{2}(-[a-z]{2})?$',
    message="Invalid language code (e.g., 'fr', 'pt-br').",
)

class LanguageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "language"
    verbose_name = "Langues"

    def ready(self):
        """
        Configure l'app language :
        - Enregistre des system checks pour valider langues actives/défaut.
        - Connecte un seed idempotent après migrations (si table vide).
        - Connecte le signal pour invalider les caches de utils.py.
        """
        from .signals import clear_language_caches  # noqa: F401  # Force signal registration

        @register(Tags.models)
        def language_checks(app_configs, **kwargs):
            """
            Vérifie la configuration des langues :
            - Présence d'au moins une langue active.
            - Présence d'une langue par défaut.
            - Unicité de la langue par défaut.
            - Langue par défaut active.
            Returns:
                List[Warning]: Liste des avertissements si problèmes détectés.
            """
            if getattr(settings, "LANG_CHECKS_DISABLE", False):
                logger.info("Langue checks désactivés via settings.LANG_CHECKS_DISABLE.")
                return []

            issues = []
            try:
                from .models import Language
                if not Language.objects.filter(is_active=True).exists():
                    issues.append(
                        Warning(
                            "Aucune langue active détectée.",
                            id="language.W001",
                            hint="Créez au moins une langue active via l'admin.",
                        )
                    )
                    logger.warning("Check W001: Aucune langue active détectée.")
                    record_metric(
                        name="language.check_failed",
                        value=1,
                        tags={"check": "W001", "description": "no_active_language"}
                    )
                if not Language.objects.filter(is_default=True).exists():
                    issues.append(
                        Warning(
                            "Aucune langue par défaut définie.",
                            id="language.W002",
                            hint="Cochez 'is_default' sur une langue active.",
                        )
                    )
                    logger.warning("Check W002: Aucune langue par défaut définie.")
                    record_metric(
                        name="language.check_failed",
                        value=1,
                        tags={"check": "W002", "description": "no_default_language"}
                    )
                if Language.objects.filter(is_default=True).count() > 1:
                    issues.append(
                        Warning(
                            "Plusieurs langues par défaut détectées.",
                            id="language.W003",
                            hint="Seule une langue doit avoir is_default=True.",
                        )
                    )
                    logger.warning("Check W003: Plusieurs langues par défaut détectées.")
                    record_metric(
                        name="language.check_failed",
                        value=1,
                        tags={"check": "W003", "description": "multiple_default_languages"}
                    )
                if Language.objects.filter(is_default=True, is_active=False).exists():
                    issues.append(
                        Warning(
                            "Langue par défaut inactive.",
                            id="language.W004",
                            hint="La langue par défaut doit avoir is_active=True.",
                        )
                    )
                    logger.warning("Check W004: Langue par défaut inactive.")
                    record_metric(
                        name="language.check_failed",
                        value=1,
                        tags={"check": "W004", "description": "default_language_inactive"}
                    )
                if not issues:
                    record_metric(
                        name="language.check_success",
                        value=1,
                        tags={"description": "all_checks_passed"}
                    )
                    logger.info("Tous les checks de langue passés avec succès.")
            except DatabaseError as e:
                logger.error(f"Erreur lors des checks de langue: {str(e)}")
                issues.append(
                    Warning(
                        "Erreur base de données lors des checks.",
                        id="language.W005",
                        hint="Vérifiez la connexion à la base de données.",
                    )
                )
                record_metric(
                    name="language.check_failed",
                    value=1,
                    tags={"check": "W005", "description": "database_error"}
                )
            return issues

        def seed_default_langs(sender, **kwargs):
            """
            Seed idempotent pour initialiser les langues si table vide.
            - Utilise settings.DEFAULT_LANG et settings.ACTIVE_LANGS comme fallbacks.
            - Valide codes langues via CODE_VALIDATOR.
            - Crée langue par défaut et langues actives, normalisées via utils.normalize_locale.
            - Invalide caches après création.
            """
            if getattr(settings, "LANG_SEED_DISABLE", False):
                logger.info("Seeding de langues désactivé via settings.LANG_SEED_DISABLE.")
                return

            try:
                from .utils import normalize_locale, clear_lang_caches
                from .models import Language

                if Language.objects.exists():
                    logger.debug("Tableau des langues non vide, seeding ignoré.")
                    return

                with transaction.atomic():
                    default_code = normalize_locale(getattr(settings, "DEFAULT_LANG", "fr"))
                    active_codes = [
                        normalize_locale(code)
                        for code in getattr(settings, "ACTIVE_LANGS", ["fr", "en"])
                    ]

                    # Validation regex
                    if default_code:
                        CODE_VALIDATOR(default_code)
                        Language.objects.get_or_create(
                            code=default_code,
                            defaults={
                                "name": default_code.upper(),
                                "is_active": True,
                                "is_default": True,
                            }
                        )
                        logger.info(f"Langue par défaut créée: {default_code}")
                        record_metric(
                            name="language.seed_success",
                            value=1,
                            tags={"code": default_code, "type": "default"}
                        )
                    for code in active_codes:
                        if code == default_code or not code:
                            continue
                        CODE_VALIDATOR(code)
                        Language.objects.get_or_create(
                            code=code,
                            defaults={
                                "name": code.upper(),
                                "is_active": True,
                                "is_default": False,
                            }
                        )
                        logger.info(f"Langue active créée: {code}")
                        record_metric(
                            name="language.seed_success",
                            value=1,
                            tags={"code": code, "type": "active"}
                        )
                    clear_lang_caches()
                    logger.debug("Caches de langues invalidés après seeding.")
            except (DatabaseError, ValidationError) as e:
                logger.error(f"Erreur lors du seeding des langues: {str(e)}")
                record_metric(
                    name="language.seed_failed",
                    value=1,
                    tags={"error": str(e)}
                )

        post_migrate.connect(
            seed_default_langs,
            sender=self,
            dispatch_uid="language_seed_default_langs"
        )

