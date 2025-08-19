from django.apps import AppConfig
from django.conf import settings
from django.core.checks import register, Error, Warning, Tags
from django.db import connection


class GlossaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.verticales.glossary"
    verbose_name = "Glossaire"

    # Pas de side-effects ici (pas d'import Celery/tasks) pour éviter les cycles.
    def ready(self):
        # Si tu avais des signaux, tu les importerais ici.
        # from . import signals  # noqa: F401
        return


@register(Tags.database)
def glossary_db_checks(app_configs, **kwargs):
    """
    Vérifie que l’environnement DB est conforme :
    - PostgreSQL
    - Extensions 'vector' (pgvector) et 'pg_trgm'
    Ces checks ne modifient rien : ils affichent seulement des erreurs/avertissements.
    """
    issues = []

    # 1) PostgreSQL requis (VectorField + JSONB + GIN/TRGM)
    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    if "postgresql" not in engine:
        issues.append(
            Error(
                "PostgreSQL est requis (VectorField pgvector + index TRGM).",
                id="glossary.E001",
                hint="Configure DATABASE_URL avec un backend postgresql, puis exécute les migrations.",
            )
        )
        return issues  # inutile d'aller plus loin si pas Postgres

    # 2) Extensions installées ?
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension;")
            installed = {row[0] for row in cur.fetchall()}

        if "vector" not in installed:
            issues.append(
                Warning(
                    "Extension PostgreSQL 'vector' absente (pgvector).",
                    id="glossary.W001",
                    hint="Ajoute une migration CREATE EXTENSION IF NOT EXISTS vector; puis migrate.",
                )
            )
        if "pg_trgm" not in installed:
            issues.append(
                Warning(
                    "Extension PostgreSQL 'pg_trgm' absente.",
                    id="glossary.W002",
                    hint="Ajoute une migration CREATE EXTENSION IF NOT EXISTS pg_trgm; puis migrate.",
                )
            )
    except Exception as e:
        # En dev (avant migrations), l’interrogation peut échouer : on remonte un warning doux.
        issues.append(
            Warning(
                f"Impossible de vérifier les extensions Postgres pour l’instant ({e}).",
                id="glossary.W003",
                hint="Exécute les migrations, puis `python manage.py check`.",
            )
        )

    return issues
