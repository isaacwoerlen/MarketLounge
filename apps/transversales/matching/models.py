# apps/verticales/matching/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from pgvector.django import VectorField
import re
import logging
import json
import numpy as np

logger = logging.getLogger(__name__)

# Import validators from utils_core
from transversales.utils_core.validators import validate_tenant_id, validate_lang, validate_checksum, validate_scope, validate_json_field

# Supported embedding models
SUPPORTED_MODELS = [
    "sentence-transformers/paraphrase-multilingual",
    # Add future models here, e.g., "all-MiniLM-L6-v2"
]

# Default embedding dimension from settings
_EMBED_DIM = getattr(settings, 'EMBEDDING_DIM', 384)

class EmbeddingItem(models.Model):
    """
    Vérité unique des embeddings pour recherche sémantique (pgvector).
    - Multi-tenancy strict via tenant_id (regex validation).
    - Unicité (tenant_id, scope, ref_id) pour un vecteur canonique par référence.
    - Vector dimension aligned with settings.EMBEDDING_DIM.
    - Checksum validated as SHA256 hex (calculation in services.py).
    """
    tenant_id = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_tenant_id],
        help_text=_("Tenant identifier (blank for default tenant)")
    )
    scope = models.CharField(
        max_length=64,
        validators=[validate_scope],
        help_text=_("Context scope (e.g., company, glossary)")
    )
    ref_id = models.CharField(
        max_length=255,
        help_text=_("Reference ID (e.g., company_id, concept_id)")
    )
    lang = models.CharField(
        max_length=10,
        validators=[validate_lang],
        help_text=_("Language code (BCP-47, e.g., fr, pt-br)")
    )
    model = models.CharField(
        max_length=100,
        choices=[(m, m) for m in SUPPORTED_MODELS],
        default=SUPPORTED_MODELS[0],
        help_text=_("Embedding model used")
    )
    dim = models.PositiveIntegerField(
        default=_EMBED_DIM,
        help_text=_("Embedding dimension (aligned with settings.EMBEDDING_DIM)")
    )
    checksum = models.CharField(
        max_length=64,
        validators=[validate_checksum],
        help_text=_("SHA256 hex of source text (computed in services.py)")
    )
    vector = VectorField(
        dimensions=_EMBED_DIM,
        help_text=_("Semantic embedding vector")
    )
    payload = models.JSONField(
        default=dict,
        validators=[validate_json_field],
        help_text=_("Additional metadata (e.g., {'sector': 'aeronautique'})")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'scope', 'ref_id'],
                name='uniq_embedding_ref',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'scope'], name='idx_tenant_scope'),
            models.Index(fields=['lang'], name='idx_lang'),
            models.Index(
                fields=['vector'],
                name='idx_embedding_cosine',
                opclasses={'vector': 'vector_cosine_ops'},
            ),
        ]

    def clean(self):
        """Validate fields and normalize lang."""
        # Normalize lang
        self.lang = validate_lang(self.lang)

        # Validate tenant_id, scope, checksum
        validate_tenant_id(self.tenant_id)
        validate_scope(self.scope)
        validate_checksum(self.checksum)

        # Validate model
        if self.model not in [choice[0] for choice in self._meta.get_field('model').choices]:
            logger.error(f"Invalid model: {self.model}")
            raise ValidationError(
                _(f"Model must be one of {', '.join([choice[0] for choice in self._meta.get_field('model').choices])}")
            )

        # Validate dim
        if self.dim not in [_EMBED_DIM, 768]:
            logger.warning(f"Unexpected dim value: {self.dim}, expected {_EMBED_DIM} or 768")
            raise ValidationError(
                _(f"Embedding dimension must be compatible with supported models (e.g., {_EMBED_DIM}, 768)")
            )

        # Validate payload
        validate_json_field(self.payload)

        super().clean()

    def save(self, *args, **kwargs):
        """Validate and normalize vector before saving."""
        self.clean()
        if self.vector is not None:
            # Normalize L2 for cosine search
            norm = np.linalg.norm(self.vector)
            if norm != 0:
                self.vector = self.vector / norm
            else:
                logger.warning(f"Zero vector for EmbeddingItem {self.scope}:{self.ref_id}, setting to null")
                self.vector = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scope}:{self.ref_id} ({self.tenant_id or 'default'}, {self.lang})"