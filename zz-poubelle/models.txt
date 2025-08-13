# apps/glossary/models.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
from django.utils import timezone

class GlossaryType(models.TextChoices):
    METIER = "metier", "Métier"
    OPERATION = "operation", "Opération"
    VARIANTE = "variante", "Variante"


class GlossaryNode(models.Model):
    """
    Source de vérité unique (Glossaire)
    - glossary_id : identifiant canonique (stable, unique, indexé)
    - node_id     : slug UX lisible (non unique, indexé) → chemins/URLs
    - parent      : FK sur glossary_id du parent (contexte métier strict)
    - labels/definition/procede/explication_technique/seo : JSON multilingue
    - embedding   : JSON (phase 1), migrable vers pgvector plus tard
    """

    # Identifiants
    glossary_id = models.CharField(max_length=64, unique=True, db_index=True)
    node_id = models.SlugField(max_length=128, unique=False, db_index=True)

    # Typage
    type = models.CharField(max_length=16, choices=GlossaryType.choices)

    # Parent par ID canonique (glossary_id)
    parent = models.ForeignKey(
        "self",
        to_field="glossary_id",
        db_column="parent_glossary_id",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    # Contexte (non identifiant)
    path = models.CharField(max_length=512, db_index=True)

    # Contenus multilingues (FR/EN requis; DE/IT faciles à ajouter)
    labels = models.JSONField(default=dict, blank=True)                   # {"fr": "...", "en": "...", "de": "...", ...}
    definition = models.JSONField(default=dict, blank=True)               # (metier, operation)
    procede = models.JSONField(default=dict, blank=True)                  # (operation)
    explication_technique = models.JSONField(default=dict, blank=True)    # (variante)
    seo = models.JSONField(default=dict, blank=True)                      # {"fr": {"keywords":[...], "description":"..."}}

    # Embedding par nœud (phase 1)
    embedding = models.JSONField(null=True, blank=True)

    # Gouvernance légère
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    alerts = models.JSONField(null=True, blank=True)  # ex: [{"type":"duplicate_node_id","detail":"..."}]

    # Trace
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        indexes = [
            models.Index(fields=["type"]),
            models.Index(fields=["path"]),
            models.Index(fields=["node_id"]),
        ]
        ordering = ["type", "glossary_id"]

    # ───────── Validations métier ─────────
    def clean(self):
        if not self.node_id:
            raise ValidationError("node_id est requis (slug snake_case).")

        # Règles parentales
        if self.type == GlossaryType.METIER:
            if self.parent is not None:
                raise ValidationError("Un 'metier' ne doit pas avoir de parent.")
        elif self.type == GlossaryType.OPERATION:
            if not self.parent or self.parent.type != GlossaryType.METIER:
                raise ValidationError("Le parent d'une 'operation' doit être un 'metier'.")
        elif self.type == GlossaryType.VARIANTE:
            if not self.parent or self.parent.type != GlossaryType.OPERATION:
                raise ValidationError("Le parent d'une 'variante' doit être une 'operation'.")

        # Contenus requis/interdits par type
        if self.type == GlossaryType.METIER:
            if self._has_nonempty(self.procede):
                raise ValidationError("Un 'metier' ne doit pas définir 'procede'.")
            if self._has_nonempty(self.explication_technique):
                raise ValidationError("Un 'metier' ne doit pas définir 'explication_technique'.")
        if self.type == GlossaryType.OPERATION:
            if not self._has_nonempty(self.definition):
                raise ValidationError("Une 'operation' doit avoir une 'definition'.")
            if not self._has_nonempty(self.procede):
                raise ValidationError("Une 'operation' doit avoir un 'procede'.")
            if self._has_nonempty(self.explication_technique):
                raise ValidationError("Une 'operation' ne doit pas définir 'explication_technique'.")
        if self.type == GlossaryType.VARIANTE:
            if not self._has_nonempty(self.explication_technique):
                raise ValidationError("Une 'variante' doit avoir une 'explication_technique'.")
            if self._has_nonempty(self.definition):
                raise ValidationError("Une 'variante' ne doit pas définir 'definition'.")
            if self._has_nonempty(self.procede):
                raise ValidationError("Une 'variante' ne doit pas définir 'procede'.")

        # Anti‑cycle
        if self.parent:
            seen = {self.glossary_id}
            p = self.parent
            while p:
                if p.glossary_id in seen:
                    raise ValidationError("Cycle détecté dans la relation parent.")
                seen.add(p.glossary_id)
                p = p.parent

        # Multilingue minimal requis
        for lang in ("fr", "en"):
            if not (self.labels or {}).get(lang):
                raise ValidationError(f"labels.{lang} est requis.")

        # SEO structure propre
        if self.seo:
            for lang, obj in self.seo.items():
                if not isinstance(obj, dict):
                    raise ValidationError(f"seo.{lang} doit être un objet.")
                if "keywords" in obj and not isinstance(obj["keywords"], list):
                    raise ValidationError(f"seo.{lang}.keywords doit être une liste.")

    # ───────── Persistance ─────────
    def save(self, *args, **kwargs):
        # Normalise le slug UX
        self.node_id = slugify(self.node_id or (self.labels or {}).get("fr") or self.glossary_id or str(uuid.uuid4()))
        # Recalcule le path
        if self.parent:
            base = self.parent.path or self.parent.node_id
            self.path = f"{base}/{self.node_id}"
        else:
            self.path = self.node_id
        # Initialise les JSON manquants
        for key in ("labels", "definition", "procede", "explication_technique", "seo"):
            if getattr(self, key) is None:
                setattr(self, key, {})
        super().save(*args, **kwargs)

    # ───────── Utils ─────────
    @staticmethod
    def _has_nonempty(dct: dict) -> bool:
        return bool(dct) and any(bool(v) for v in dct.values())

    def __str__(self):
        return f"{self.glossary_id} / {self.node_id} [{self.type}]"
