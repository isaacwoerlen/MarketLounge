# apps/glossary/models.py
from __future__ import annotations

import uuid
from typing import Optional, Set

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.db import migrations


# Langues couvertes pour la concat de recherche (ajuste si besoin)
SEARCH_LANGS = ("fr", "en", "de", "it")


class GlossaryType(models.TextChoices):
    METIER = "metier", "Métier"
    OPERATION = "operation", "Opération"
    VARIANTE = "variante", "Variante"


class GlossaryNode(models.Model):
    """
    Nœud de Glossaire gouverné (Pilier 1) :
    - Identifiant canonique: glossary_id (unique)
    - Slug UX: node_id (lisible, non unique globalement)
    - Hiérarchie: parent → FK vers 'glossary_id' (db_column = parent_glossary_id)
    - Chemin: path (dérivé, indexé)
    - Contenu: labels/definition/procede/explication_technique/seo (JSONB)
    - Gouvernance: version, is_active, created_by/reviewed_by, alerts
    - Performance: search_text (trigram), indexes GIN sur JSONB
    """

    # Identifiants
    glossary_id = models.CharField(max_length=100, unique=True, db_index=True)
    node_id = models.CharField(max_length=100, db_index=True)

    # Typage
    type = models.CharField(max_length=20, choices=GlossaryType.choices, db_index=True)

    # Arborescence (FK via 'glossary_id' pour des URLs/API stables)
    parent = models.ForeignKey(
        "self",
        to_field="glossary_id",
        db_column="parent_glossary_id",
        related_name="children",
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # évite la suppression accidentelle d'une branche
    )

    # Chemin dérivé (ex: forge/forge_libre/marteau_pilon)
    path = models.CharField(max_length=255, db_index=True)

    # Champs JSONB multilingues
    labels = models.JSONField(default=dict, blank=True)  # {"fr": "...", "en": "...", ...}
    definition = models.JSONField(default=dict, blank=True)
    procede = models.JSONField(default=dict, blank=True)
    explication_technique = models.JSONField(default=dict, blank=True)
    seo = models.JSONField(default=dict, blank=True)  # {"fr": {"keywords": [...], "description": "..."}}

    # Embedding (optionnel) et alerts (liste d’objets)
    embedding = models.JSONField(null=True, blank=True)
    alerts = models.JSONField(default=list, blank=True)  # ex: [{"type":"duplicate","detail":"..."}]

    # Recherche plein-texte légère (trigram sur un concat labels/keywords)
    search_text = models.TextField(blank=True, default="")

    # Gouvernance & timestamps
    is_active = models.BooleanField(default=False)
    version = models.IntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    # ---------- Validation métier (Pilier 1) ----------

    def clean(self):
        """
        Règles clés :
        - Métier : pas de parent
        - Opération : parent obligatoire et de type Métier
        - Variante : parent obligatoire et de type Opération
        - Anti-cycle dans l’arbre
        - Publication stricte : interdit is_active=True sans revue
        """
        t = self.type

        # Parentage de base
        if t == GlossaryType.METIER and self.parent is not None:
            raise ValidationError("Un 'métier' ne doit pas avoir de parent.")
        if t == GlossaryType.OPERATION and self.parent is None:
            raise ValidationError("Une 'opération' doit avoir un parent de type 'métier'.")
        if t == GlossaryType.VARIANTE and self.parent is None:
            raise ValidationError("Une 'variante' doit avoir un parent de type 'opération'.")

        # Typage du parent (si présent)
        if self.parent:
            if t == GlossaryType.OPERATION and self.parent.type != GlossaryType.METIER:
                raise ValidationError("Le parent d'une 'opération' doit être un 'métier'.")
            if t == GlossaryType.VARIANTE and self.parent.type != GlossaryType.OPERATION:
                raise ValidationError("Le parent d'une 'variante' doit être une 'opération'.")

        # Anti-cycle (remonte les ancêtres par glossary_id)
        if self.parent:
            seen: Set[str] = set()
            cursor: Optional[GlossaryNode] = self.parent
            while cursor:
                if cursor.glossary_id in seen:
                    raise ValidationError("Cycle détecté dans l'arborescence du glossaire.")
                seen.add(cursor.glossary_id)
                if cursor == self:
                    raise ValidationError("Un nœud ne peut pas être son propre ancêtre.")
                cursor = cursor.parent

        # Gouvernance : publication stricte
        if self.is_active:
            if self.reviewed_by is None or (self.version or 0) < 2:
                raise ValidationError(
                    "Publication interdite sans validation humaine : 'reviewed_by' requis et version >= 2."
                )

    # ---------- Sauvegarde (normalisation + path + search_text) ----------

    def save(self, *args, **kwargs):
        """
        - Génère/normalise node_id (slug) à partir du label FR/EN ou de glossary_id
        - Recalcule path à partir du parent (ou node_id si racine)
        - Initialise les JSONB manquants
        - Construit search_text (labels + keywords SEO) pour index trigram
        - Place un alert IA minimal si création 'bot' sans labels
        """
        if not self.glossary_id:
            self.glossary_id = f"{self.type}_{str(uuid.uuid4())[:8]}"
        super().save(*args, **kwargs)
       
        # 1) node_id lisible & stable
        base_label = None
        if isinstance(self.labels, dict):
            base_label = self.labels.get("fr") or self.labels.get("en")
        self.node_id = slugify(self.node_id or base_label or self.glossary_id or str(uuid.uuid4()))

        # 2) path hiérarchique
        if self.parent:
            parent_path = getattr(self.parent, "_cached_path", None) or self.parent.path or self.parent.node_id
            self.path = f"{parent_path}/{self.node_id}"
        else:
            self.path = self.node_id

        # 3) JSONB par défaut
        if self.labels is None:
            self.labels = {}
        if self.definition is None:
            self.definition = {}
        if self.procede is None:
            self.procede = {}
        if self.explication_technique is None:
            self.explication_technique = {}
        if self.seo is None:
            self.seo = {}
        if self.alerts is None:
            self.alerts = []

        # 4) search_text (labels + seo.keywords FR/EN…)
        def _kw(lang: str) -> str:
            v = (self.seo or {}).get(lang, {})
            if isinstance(v, dict):
                kws = v.get("keywords") or []
                if isinstance(kws, (list, tuple)):
                    return " ".join([str(x) for x in kws])
                return str(kws)
            return ""
        buckets = []
        for lang in SEARCH_LANGS:
            buckets.append((self.labels or {}).get(lang, ""))
            buckets.append(_kw(lang))
        self.search_text = " ".join([b for b in buckets if b]).strip()

        # 5) petit signal IA si création par bot et contenu vide
        if getattr(self, "created_by", None) and not self.labels:
            self.alerts = (self.alerts or []) + [{"type": "ia_pending", "detail": "Labels à générer via IA"}]

        super().save(*args, **kwargs)

        # cache local optionnel pour chaines de sauvegarde (non persistant)
        self._cached_path = self.path

    # ---------- Aides & représentation ----------

    @property
    def parent_glossary_id(self) -> Optional[str]:
        return self.parent.glossary_id if self.parent else None

    @property
    def depth(self) -> int:
        # profondeur simple dérivée du path
        return self.path.count("/") + 1 if self.path else 0

    def __str__(self) -> str:
        return f"[{self.type}] {self.glossary_id} → {self.path}"

    class Meta:
        verbose_name = "Nœud du Glossaire"
        verbose_name_plural = "Nœuds du Glossaire"
        # Unicité “fratrie”: même parent → node_id unique (sécurise la structure)
        constraints = [
            models.UniqueConstraint(fields=["parent", "node_id"], name="uq_gloss_parent_node"),
        ]
        indexes = [
            models.Index(fields=['glossary_id']),
            models.Index(fields=["type"]),
            models.Index(fields=["path"]),
            models.Index(fields=["node_id"]),
            # Indexe la FK parent pour des listes enfants instantanées
            models.Index(fields=["parent"]),
            # JSONB GIN pour __contains & co
            GinIndex(fields=["labels"], name="gloss_labels_gin"),
            GinIndex(fields=["definition"], name="gloss_definition_gin"),
            GinIndex(fields=["procede"], name="gloss_procede_gin"),
            GinIndex(fields=["explication_technique"], name="gloss_exptech_gin"),
            GinIndex(fields=["seo"], name="gloss_seo_gin"),
            GinIndex(fields=["alerts"], name="gloss_alerts_gin"),
            # Trigram pour icontains sur search_text (nécessite l’extension pg_trgm)
            GinIndex(fields=["search_text"], name="gloss_search_trgm", opclasses=["gin_trgm_ops"]),
            # Aide aux exports: actifs récents
            models.Index(fields=["is_active", "version"], name="idx_active_version"),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    # Migration pour pg_trgm
    class Migration(migrations.Migration):
        dependencies = [
            ('glossary', 'previous_migration'),  # Remplacer par votre dernière migration
        ]
        operations = [
            migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS pg_trgm;"),
        ]
