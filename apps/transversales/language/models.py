# apps/transversales/language/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from pgvector.django import VectorField, HnswIndex
from utils_core.validators import validate_tenant_id, validate_lang, normalize_locale, validate_checksum, validate_scope, validate_json_field
from utils_core.text_cleaning import normalize_text
from utils_core.types import TranslationPayload, TranslationJobPayload
from utils_core.env import get_env_variable
import logging
import numpy as np
import json
import uuid

logger = logging.getLogger(__name__)

# --- Configuration ---
LANG_CACHE_TTL = get_env_variable("LANG_CACHE_TTL", cast="int", default=60)
DEFAULT_LANG = get_env_variable("DEFAULT_LANG", cast="str", default="fr")

# --- Manager ---
class LanguageManager(models.Manager):
    """
    Manager pour Language avec cache pour langues actives/défaut.
    Utilisé dans language pour traductions, matching pour queries multilingues, curation pour validations.
    """
    def get_default(self):
        """
        Récupère le code de la langue par défaut avec cache.
        Returns:
            str: Code de langue par défaut (ex. : 'fr').
        
        Example:
            >>> from .models import Language
            >>> Language.objects.get_default()  # language: default source lang
            'fr'
        """
        def _compute():
            obj = (self.filter(is_default=True).first()
                   or self.filter(is_active=True).order_by('priority', 'code').first())
            return obj.code if obj else DEFAULT_LANG
        try:
            result = cache.get_or_set(_ck("default"), _compute, timeout=LANG_CACHE_TTL)
            logger.debug(f"Langue par défaut récupérée: {result}")
            return result
        except Exception as e:
            logger.error(f"Erreur récupération langue par défaut: {str(e)}")
            return DEFAULT_LANG

    def get_active(self):
        """
        Récupère la liste des codes de langues actives avec cache.
        Returns:
            List[str]: Liste des codes (ex. : ['fr', 'en', 'es']).
        
        Example:
            >>> from .models import Language
            >>> Language.objects.get_active()  # matching: filter query langs
            ['fr', 'en', 'es']
        """
        def _compute():
            return list(self.filter(is_active=True).order_by('priority', 'code').values_list('code', flat=True))
        try:
            result = cache.get_or_set(_ck("active"), _compute, timeout=LANG_CACHE_TTL)
            logger.debug(f"Langues actives récupérées: {result}")
            return result
        except Exception as e:
            logger.error(f"Erreur récupération langues actives: {str(e)}")
            return []

def _ck(key: str) -> str:
    return f"lang:{key}"

# --- Language ---
class Language(models.Model):
    """
    Langue avec statut actif/défaut et priorité batch.
    """
    code = models.CharField(
        max_length=10,
        unique=True,
        validators=[validate_lang],
        help_text=_("Language code (BCP-47, e.g., fr, pt-br)")
    )
    name = models.CharField(
        max_length=100,
        help_text=_("Human-readable name (e.g., Français)")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Is language active for translation?")
    )
    is_default = models.BooleanField(
        default=False,
        help_text=_("Is default language?")
    )
    priority = models.PositiveIntegerField(
        default=5,
        help_text=_("Batch priority (1=high, 10=low)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LanguageManager()

    class Meta:
        verbose_name = _("Language")
        verbose_name_plural = _("Languages")
        unique_together = []
        indexes = [
            models.Index(fields=['is_active', 'priority'], name='idx_lang_active_priority'),
            models.Index(fields=['code'], name='idx_lang_code'),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Validate constraints (unique default, default active)."""
        self.code = normalize_locale(self.code)
        validate_lang(self.code)
        if self.is_default:
            if Language.objects.filter(is_default=True).exclude(pk=self.pk).exists():
                raise ValidationError(_("Only one default language allowed"))
            if not self.is_active:
                raise ValidationError(_("Default language must be active"))
        super().clean()

    def save(self, *args, **kwargs):
        """Normalize code and invalidate cache."""
        self.full_clean()
        super().save(*args, **kwargs)
        cache.delete_many([_ck("default"), _ck("active")])

# --- TranslatableKey ---
class TranslatableKey(models.Model):
    """
    Clé traduisible (ex. : seo:title, glossary:op:soudure).
    - Multi-tenancy via tenant_id.
    - Unicité (scope, key, tenant_id).
    - JSON pour prompt_template (ex. : {"tone": "formal"}).
    """
    tenant_id = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_tenant_id],
        help_text=_("Tenant identifier (blank for default)")
    )
    scope = models.CharField(
        max_length=64,
        validators=[validate_scope],
        help_text=_("Scope (e.g., glossary, seo:title)")
    )
    key = models.CharField(
        max_length=255,
        help_text=_("Key (e.g., op:soudure)")
    )
    text = models.TextField(
        blank=True,
        help_text=_("Source text (if applicable)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    prompt_template = models.JSONField(
        default=dict,
        validators=[validate_json_field],
        help_text=_("Prompt template for LLM (e.g., {'tone': 'formal'})")
    )

    class Meta:
        verbose_name = _("Translatable Key")
        verbose_name_plural = _("Translatable Keys")
        unique_together = ['tenant_id', 'scope', 'key']
        indexes = [
            models.Index(fields=['tenant_id', 'scope'], name='idx_tk_tenant_scope'),
            models.Index(fields=['key'], name='idx_tk_key'),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key} ({self.tenant_id or 'default'})"

    def clean(self):
        """Validate fields."""
        validate_json_field(self.prompt_template)
        validate_tenant_id(self.tenant_id)
        validate_scope(self.scope)
        super().clean()

# --- Translation ---
class Translation(models.Model):
    """
    Traduction pour une clé et langue spécifique.
    - Multi-tenancy via tenant_id.
    - Unicité (key, language, tenant_id).
    - JSON pour alerts (ex. : SEO warnings).
    - VectorField pour embeddings (pgvector).
    - Checksum pour idempotence.
    - Origin (human, llm, tm).
    """
    key = models.ForeignKey(
        TranslatableKey,
        on_delete=models.CASCADE,
        related_name="translations",
        help_text=_("Translatable key")
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="translations",
        help_text=_("Language")
    )
    tenant_id = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_tenant_id],
        help_text=_("Tenant identifier (blank for default)")
    )
    text = models.TextField(
        help_text=_("Translated text")
    )
    source_checksum = models.CharField(
        max_length=64,
        validators=[validate_checksum],
        help_text=_("SHA256 checksum of source text")
    )
    origin = models.CharField(
        max_length=20,
        choices=[
            ("human", "Human"),
            ("llm", "LLM"),
            ("tm", "TM")
        ],
        default="llm",
        help_text=_("Origin (human, llm, tm)")
    )
    alerts = models.JSONField(
        default=list,
        validators=[validate_json_field],
        help_text=_("Alerts (e.g., SEO warnings)")
    )
    embedding = VectorField(
        dimensions=get_env_variable("LANG_EMBEDDING_DIM", cast="int", default=384),
        null=True,
        blank=True,
        help_text=_("Embedding vector (pgvector)")
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text=_("Version (incremented on update)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    provider_info = models.JSONField(
        default=dict,
        validators=[validate_json_field],
        help_text=_("Provider info (e.g., {'provider': 'mistral'})")
    )
    domain = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Domain (e.g., homepage)")
    )

    class Meta:
        verbose_name = _("Translation")
        verbose_name_plural = _("Translations")
        unique_together = ['key', 'language', 'tenant_id']
        indexes = [
            models.Index(fields=['tenant_id', 'key', 'language'], name='idx_trans_tenant_key_lang'),
            models.Index(fields=['source_checksum'], name='idx_trans_checksum'),
            HnswIndex(
                name='idx_trans_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=100,
                opclasses={'embedding': 'vector_cosine_ops'}
            ),
        ]

    def __str__(self):
        return f"{self.key.scope}:{self.key.key} ({self.language.code}, v{self.version})"

    def clean(self):
        """Validate fields and normalize."""
        validate_lang(self.language.code)
        validate_tenant_id(self.tenant_id)
        validate_json_field(self.alerts)
        validate_json_field(self.provider_info)
        if self.alerts and any('type' not in alert or 'field' not in alert or 'message' not in alert for alert in self.alerts):
            raise ValidationError(_("Each alert must be a dict with 'type', 'field', 'message'"))
        if self.provider_info and not isinstance(self.provider_info.get('provider', ''), str):
            raise ValidationError(_("provider_info must have a 'provider' key as string"))
        super().clean()

    def save(self, *args, **kwargs):
        """Normalize text and embedding L2 before saving."""
        self.text = normalize_text(self.text, remove_accents_flag=False, lowercase=False)
        self.source_checksum = compute_checksum(self.text)  # Ensure checksum matches normalized text
        if self.embedding is not None:
            norm = np.linalg.norm(self.embedding)
            if norm != 0:
                self.embedding = self.embedding / norm
            else:
                logger.warning(f"Zero embedding for Translation {self.key.scope}:{self.key.key}, setting to null")
                self.embedding = None
        super().save(*args, **kwargs)

    def to_payload(self) -> TranslationPayload:
        """
        Convert to typed payload for API/serialization.
        Example:
            >>> translation = Translation.objects.get(id=1)
            >>> translation.to_payload()  # language: API response
            {'key': 'soudure', 'scope': 'glossary', 'lang': 'fr', ...}
        """
        return TranslationPayload(
            key=self.key.key,
            scope=self.key.scope,
            lang=self.language.code,
            text=self.text,
            tenant_id=self.tenant_id,
            version=self.version,
            alerts=self.alerts,
            embedding=self.embedding,
            source_checksum=self.source_checksum,
            origin=self.origin,
            provider_info=self.provider_info,
            domain=self.domain,
        )

# --- TranslationJob ---
class TranslationJob(models.Model):
    """
    Job de traduction batch.
    """
    name = models.CharField(
        max_length=100,
        help_text=_("Job name")
    )
    state = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed")
        ],
        default="pending",
        help_text=_("Job state")
    )
    source_locale = models.CharField(
        max_length=10,
        validators=[validate_lang],
        help_text=_("Source locale")
    )
    target_locales = models.JSONField(
        validators=[validate_json_field],
        help_text=_("Target locales list")
    )
    scope_filter = models.JSONField(
        default=list,
        validators=[validate_json_field],
        help_text=_("Scope filters")
    )
    stats = models.JSONField(
        default=dict,
        validators=[validate_json_field],
        help_text=_("Stats")
    )
    errors = models.JSONField(
        default=list,
        validators=[validate_json_field],
        help_text=_("Errors")
    )
    glossary_ids = models.JSONField(
        default=list,
        validators=[validate_json_field],
        help_text=_("Glossary IDs")
    )
    tenant_id = models.CharField(
        max_length=36,
        null=True,
        validators=[validate_tenant_id],
        help_text=_("Tenant identifier")
    )
    priority = models.PositiveIntegerField(
        default=5,
        help_text=_("Job priority (1=high)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Translation Job")
        verbose_name_plural = _("Translation Jobs")
        indexes = [
            models.Index(fields=['tenant_id', 'state'], name='idx_tjob_tenant_state'),
            models.Index(fields=['priority', 'created_at'], name='idx_tjob_priority_created'),
        ]

    def __str__(self):
        return f"{self.name} ({self.state})"

    def clean(self):
        """Validate fields."""
        self.source_locale = normalize_locale(self.source_locale)
        validate_lang(self.source_locale)
        self.target_locales = [normalize_locale(lang) for lang in self.target_locales]
        for lang in self.target_locales:
            validate_lang(lang)
        validate_tenant_id(self.tenant_id)
        validate_json_field(self.scope_filter)
        validate_json_field(self.stats)
        validate_json_field(self.errors)
        validate_json_field(self.glossary_ids)
        super().clean()

    def to_payload(self) -> TranslationJobPayload:
        """
        Convert to typed payload for API/serialization.
        Example:
            >>> job = TranslationJob.objects.get(id=1)
            >>> job.to_payload()  # language: API response
            {'name': 'batch_1', 'state': 'done', 'source_locale': 'fr', ...}
        """
        return TranslationJobPayload(
            name=self.name,
            state=self.state,
            source_locale=self.source_locale,
            target_locales=self.target_locales,
            scope_filter=self.scope_filter,
            stats=self.stats,
            errors=self.errors,
            glossary_ids=self.glossary_ids,
            tenant_id=self.tenant_id,
            priority=self.priority,
            created_at=self.created_at.isoformat(),
            updated_at=self.updated_at.isoformat(),
        )

@receiver(pre_save, sender=Language)
def language_pre_save(sender, instance, **kwargs):
    """Invalidate cache on save."""
    cache.delete_many([_ck("default"), _ck("active")])

@receiver(pre_save, sender=TranslationJob)
def translation_job_pre_save(sender, instance, **kwargs):
    """Validate tenant_id and locales."""
    instance.clean()