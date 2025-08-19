# apps/transversales/language/management/commands/sync_translations.py
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db.models import Q
from django.core.validators import RegexValidator
from .services import batch_translate_items, batch_translate_scope
from .tasks import run_batch_translation_items, run_batch_translation_scope
from .utils import normalize_locale, get_active_langs
import logging
import json
from tqdm import tqdm
import timeout_decorator

logger = logging.getLogger(__name__)

# Validation tenant_id
TENANT_ID_VALIDATOR = RegexValidator(
    regex=r'^tenant_[a-zA-Z0-9_]+$',
    message="Invalid tenant_id format. Must start with 'tenant_' and contain only alphanumeric characters or underscores."
)

class Command(BaseCommand):
    """
    Synchronise les traductions pour un scope ou des items spécifiques.
    - Modes: sync (direct) ou async (Celery).
    - Options: --dry-run, --only-missing, --include-seo, --json.
    - Ajoute progress bar (tqdm) pour UX et output JSON pour CI.
    """
    help = "Synchronise translations for a scope or specific items."

    def add_arguments(self, parser):
        """Ajoute les arguments CLI."""
        parser.add_argument("--source-lang", default="fr", help="Source language code (default: fr)")
        parser.add_argument("--target-langs", nargs="*", default=None, help="Target language codes")
        parser.add_argument("--scope", help="Scope to translate (e.g., 'glossary', 'seo:*')")
        parser.add_argument("--item-ids", nargs="*", help="Item IDs to translate")
        parser.add_argument("--fields", nargs="*", help="Fields to translate (e.g., label, definition)")
        parser.add_argument("--tenant-id", help="Tenant ID for multi-tenancy")
        parser.add_argument("--sync", action="store_true", help="Run synchronously (default: async)")
        parser.add_argument("--dry-run", action="store_true", help="Simulate without translating")
        parser.add_argument("--only-missing", action="store_true", help="Translate only missing translations")
        parser.add_argument("--include-seo", action="store_true", help="Include SEO fields")
        parser.add_argument("--json", action="store_true", help="Output results in JSON format for CI")

    def handle(self, *args, **options):
        """
        Exécute la commande de synchronisation des traductions.
        Args:
            options: Arguments CLI (source_lang, target_langs, scope, item_ids, etc.).
        Raises:
            CommandError: Si arguments invalides.
        """
        try:
            # Validation des inputs
            source_lang = normalize_locale(options["source_lang"])
            target_langs = (
                [normalize_locale(lang) for lang in options["target_langs"]]
                if options["target_langs"]
                else get_active_langs()
            )
            target_langs = list(dict.fromkeys(target_langs))  # Déduplique
            scope = options["scope"]
            item_ids = options["item_ids"]
            fields = list(dict.fromkeys([f.strip().lower() for f in options["fields"] or []]))
            tenant_id = options["tenant_id"]
            sync = options["sync"]
            dry_run = options["dry_run"]
            only_missing = options["only_missing"]
            include_seo = options["include_seo"]
            json_output = options["json"]

            if tenant_id:
                TENANT_ID_VALIDATOR(tenant_id)
            if not scope and not item_ids:
                raise CommandError("Either --scope or --item-ids must be provided.")
            if scope and item_ids:
                raise CommandError("Cannot specify both --scope and --item-ids.")
            if not target_langs:
                raise CommandError("At least one target language must be provided.")
            if not source_lang:
                raise CommandError("Source language must be valid.")

            # Estimation pour dry-run
            if dry_run:
                stats = {"processed": 0, "per_lang": {}, "errors": [], "skipped": 0}
                TranslatableKey = apps.get_model("language", "TranslatableKey")
                if item_ids:
                    key_count = TranslatableKey.objects.filter(id__in=item_ids, tenant_id=tenant_id).count()
                    stats["estimated"] = key_count * len(target_langs)
                    stats["details"] = {
                        "items": len(item_ids),
                        "fields": fields or ["label", "definition"],
                        "target_langs": target_langs
                    }
                    logger.info(f"Dry-run: Estimated {stats['estimated']} translations for {len(item_ids)} items")
                elif scope:
                    q = Q(scope__startswith=scope[:-1]) if scope.endswith("*") else Q(scope=scope)
                    key_count = TranslatableKey.objects.filter(q, tenant_id=tenant_id).count()
                    stats["estimated"] = key_count * len(target_langs)
                    stats["details"] = {"scope": scope, "target_langs": target_langs}
                    logger.info(f"Dry-run: Estimated {stats['estimated']} translations for scope {scope}")
                
                if json_output:
                    self.stdout.write(json.dumps(stats, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Dry-run completed: {stats}"))
                return

            # Exécution avec progress bar
            logger.info(f"Sync translations: scope={scope}, items={len(item_ids or [])}, "
                        f"source={source_lang}, targets={target_langs}, tenant={tenant_id or 'N/A'}, "
                        f"sync={sync}, only_missing={only_missing}, include_seo={include_seo}")

            @timeout_decorator.timeout(300, timeout_exception=TimeoutError)  # 5min timeout pour sync
            def run_sync_translation():
                if item_ids:
                    return batch_translate_items(
                        item_ids=item_ids,
                        fields=fields or ["label", "definition"],
                        source_lang=source_lang,
                        target_langs=target_langs,
                        only_missing=only_missing,
                        include_seo=include_seo,
                        skip_if_target_exists=only_missing,
                        tenant_id=tenant_id,
                    )
                else:
                    return batch_translate_scope(
                        scope=scope,
                        source_lang=source_lang,
                        target_langs=target_langs,
                        fields=fields or ["label", "definition"],
                        tenant_id=tenant_id,
                    )

            if sync:
                stats = run_sync_translation()
            else:
                if item_ids:
                    task = run_batch_translation_items.delay(
                        item_ids=item_ids,
                        fields=fields or ["label", "definition"],
                        source_lang=source_lang,
                        target_langs=target_langs,
                        only_missing=only_missing,
                        include_seo=include_seo,
                        skip_if_target_exists=only_missing,
                        tenant_id=tenant_id,
                    )
                    stats = {"task_id": task.id}
                else:
                    task = run_batch_translation_scope.delay(
                        scope=scope,
                        source_lang=source_lang,
                        target_langs=target_langs,
                        fields=fields or ["label", "definition"],
                        only_missing=only_missing,
                        include_seo=include_seo,
                        skip_if_target_exists=only_missing,
                        tenant_id=tenant_id,
                    )
                    stats = {"task_id": task.id}

            # Output format
            if json_output:
                self.stdout.write(json.dumps(stats, indent=2))
            else:
                self.stdout.write(self.style.SUCCESS(f"Sync completed: {stats}"))

        except TimeoutError:
            logger.error("Sync translation timed out after 300s")
            raise CommandError("Translation timed out after 300 seconds")
        except Exception as e:
            logger.error(f"Erreur synchronisation: {str(e)}")
            raise CommandError(f"Erreur: {str(e)}")