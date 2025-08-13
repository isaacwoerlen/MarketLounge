# apps/glossary/apps.py
from django.apps import AppConfig


class GlossaryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.glossary'
    verbose_name = 'Glossaire'  # Human-readable name for admin