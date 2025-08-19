# apps/glossary/models.py
# NOTE: 'embedding', 'alerts' et la génération IA sont gérés par des jobs Celery
# (apps.glossary.tasks / management command). Ne pas déclencher de tâches ici.

from __future__ import annotations
import uuid
from typing import Optional, Set, List
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify
from pgvector.django import VectorField
from apps.language.utils import get_active_langs
from django.contrib.contenttypes.fields import GenericRelation
from apps.seo.models import SEOBlock

class GlossaryType(models.TextChoices):
    METIER = "metier", "Métier"
    OPERATION = "operation", "Opération"
    VARIANTE = "variante", "Variante"


class GlossaryNode(models.Model):
    """
    Nœud gouverné du Glossaire (Pilier 1)
    - Identifiant canonique immuable : glossary_id (unique)
    - Slug UX lisible : node_id (unique par parent)
    - Hiérarchie : parent -> FK (to_field='glossary_id', PROTECT)
    - Chemin déterministe : path (dérivé, indexé)
    - Contenu multilingue : labels / definition / procede / explication_technique / seo (JSON)
    - Observabilité : alerts (JSON), search_text (trigram), embedding (pgvector)
    - Gouvernance : is_active, version, created_by, reviewed_by, timestamps
    """
    glossary_id = models.CharField(max_length=100, unique=True, db_index=True, editable=False)
    node_id = models.CharField(max_length=100, db_index=True)
    type = models.CharField(max_length=20, choices=GlossaryType.choices, db_index=True)

    parent = models.ForeignKey(
        "self",
        to_field="glossary_id",
        db_column="parent_glossary_id",
        related_name="children",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )

    path = models.CharField(max_length=255, db_index=True)

    # Contenus (multilingue possible via JSON)
    labels = models.JSONField(default=dict, blank=True)
    definition = models.JSONField(default=dict, blank=True)
    procede = models.JSONField(default=dict, blank=True)
    explication_technique = models.JSONField(default=dict, blank=True)
    seo = models.JSONField(default=dict, blank=True)

    seo_blocks = GenericRelation(SEOBlock)

    # Recherche & IA
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM, null=True, blank=True)
    alerts = models.JSONField(default=list, blank=True)
    search_text = models.TextField(blank=True, default="")

    # Gouvernance
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

    # ---------- Validations métier ----------
    def clean(self):
        # --- Schéma minimal des alertes ---
        if self.alerts is None:
            self.alerts = []
        if not isinstance(self.alerts, list):
            raise ValidationError("alerts doit être une liste.")
        for a in self.alerts:
            if not isinstance(a, dict) or "type" not in a or "detail" not in a:
                raise ValidationError("Chaque alerte doit être un dict avec 'type' et 'detail'.")

        # Règles de hiérarchie
        if t == GlossaryType.METIER and self.parent is not None:
            raise ValidationError("Un 'métier' ne doit pas avoir de parent.")
        if t == GlossaryType.OPERATION and self.parent is None:
            raise ValidationError("Une 'opération' doit avoir un parent de type 'métier'.")
        if t == GlossaryType.VARIANTE and self.parent is None:
            raise ValidationError("Une 'variante' doit avoir un parent de type 'opération'.")

        if self.parent:
            if t == GlossaryType.OPERATION and self.parent.type != GlossaryType.METIER:
                raise ValidationError("Le parent d'une 'opération' doit être un 'métier'.")
            if t == GlossaryType.VARIANTE and self.parent.type != GlossaryType.OPERATION:
                raise ValidationError("Le parent d'une 'variante' doit être une 'opération'.")

            # Anti-cycles
            seen: Set[str] = set()
            cursor: Optional["GlossaryNode"] = self.parent
            while cursor:
                if cursor.glossary_id in seen:
                    raise ValidationError("Cycle détecté dans l'arborescence du glossaire.")
                seen.add(cursor.glossary_id)
                if cursor == self:
                    raise ValidationError("Un nœud ne peut pas être son propre ancêtre.")
                cursor = cursor.parent

        # Règles de publication
        if self.is_active and (self.reviewed_by is None or (self.version or 0) < 2):
            raise ValidationError(
                "Publication interdite sans validation humaine : 'reviewed_by' requis et version >= 2."
            )

    # ---------- Helpers internes ----------
    def _compute_node_id(self) -> str:
        base_label = None
        if isinstance(self.labels, dict):
            base_label = self.labels.get("fr") or self.labels.get("en")
        return slugify(self.node_id or base_label or self.glossary_id or str(uuid.uuid4()))

    def _compute_path(self) -> str:
        if self.parent:
            parent_path = self.parent.path or self.parent.node_id
            return f"{parent_path}/{self.node_id}".strip("/")
        return self.node_id

    def _compute_search_text(self) -> str:
        def _kw(lang: str) -> str:
            v = (self.seo or {}).get(lang, {})
            if isinstance(v, dict):
                kws = v.get("keywords") or []
                if isinstance(kws, (list, tuple)):
                    return " ".join([str(x) for x in kws])
                return str(kws)
            return ""

        buckets: List[str] = []
        for lang in SEARCH_LANGS:
            buckets.append((self.labels or {}).get(lang, ""))
            # (+) on ajoute aussi la définition si c'est du texte
            defv = (self.definition or {}).get(lang)
            if isinstance(defv, str):
                buckets.append(defv)
            buckets.append(_kw(lang))

        return " ".join([b for b in buckets if b]).strip()

    def _normalize_json_fields(self):
        # Garantir des structures JSON stables et du bon type
        self.labels = self.labels if isinstance(self.labels, dict) else {}
        self.definition = self.definition if isinstance(self.definition, dict) else {}
        self.procede = self.procede if isinstance(self.procede, dict) else {}
        self.explication_technique = self.explication_technique if isinstance(self.explication_technique, dict) else {}
        self.seo = self.seo if isinstance(self.seo, dict) else {}
        self.alerts = self.alerts if isinstance(self.alerts, list) else []

    def _rebuild_descendants_paths(self, old_prefix: str):
        """
        Recalcule les path de tous les descendants si le path courant a changé.
        """
        if not old_prefix or old_prefix == self.path:
            return

        new_prefix = self.path
        # Récupère tous les descendants via un startswith du chemin
        descendants = GlossaryNode.objects.filter(path__startswith=f"{old_prefix}/").only("id", "path")
        updates: List[GlossaryNode] = []
        for child in descendants:
            # Remplace uniquement la première occurrence en tête
            child.path = child.path.replace(old_prefix, new_prefix, 1)
            updates.append(child)

        if updates:
            GlossaryNode.objects.bulk_update(updates, ["path"])

    # ---------- Persistance ----------
    @transaction.atomic
    def save(self, *args, **kwargs):
        # ID canonique immuable : initialisé à la création seulement
        creating = not bool(self.pk)
        old_path = None

        if creating:
            if not self.glossary_id:
                self.glossary_id = f"{self.type}_{str(uuid.uuid4())[:8]}"
        else:
            # On récupère l'ancien path pour détecter un changement
            old = GlossaryNode.objects.only("path").get(pk=self.pk)
            old_path = old.path

        # Normalisation des structures JSON
        self._normalize_json_fields()

        # Calcule node_id / path / search_text AVANT d'écrire
        self.node_id = self._compute_node_id()
        self.path = self._compute_path()
        self.search_text = self._compute_search_text()

        # Si aucune étiquette et création pilotée, on log une alerte IA
        if getattr(self, "created_by", None) and creating and not self.labels:
            self.alerts.append({"type": "ia_pending", "detail": "Labels à générer via IA"})

        super().save(*args, **kwargs)  # une seule écriture DB

        # Si le path a changé (changement de parent/node), on propage aux descendants
        if old_path and old_path != self.path:
            self._rebuild_descendants_paths(old_path)

    # ---------- Propriétés ----------
    @property
    def parent_glossary_id(self) -> Optional[str]:
        return self.parent.glossary_id if self.parent else None

    @property
    def depth(self) -> int:
        return self.path.count("/") + 1 if self.path else 0

    def __str__(self) -> str:
        label = (self.labels or {}).get("fr") or (self.labels or {}).get("en") or self.node_id or self.glossary_id
        return f"[{self.type}] {label} ({self.path or ''})"

    class Meta:
        verbose_name = "Nœud du Glossaire"
        verbose_name_plural = "Nœuds du Glossaire"
        constraints = [
            # Unicité du slug lisible par parent (autorise le même node_id dans des branches différentes)
            models.UniqueConstraint(fields=["parent", "node_id"], name="uq_gloss_parent_node"),
        ]
        indexes = [
            models.Index(fields=["glossary_id"]),
            models.Index(fields=["type"]),
            models.Index(fields=["path"]),
            models.Index(fields=["node_id"]),
            models.Index(fields=["parent"]),
            # JSONB GIN pour chaque payload
            GinIndex(fields=["labels"], name="gloss_labels_gin"),
            GinIndex(fields=["definition"], name="gloss_definition_gin"),
            GinIndex(fields=["procede"], name="gloss_procede_gin"),
            GinIndex(fields=["explication_technique"], name="gloss_exptech_gin"),
            GinIndex(fields=["seo"], name="gloss_seo_gin"),
            GinIndex(fields=["alerts"], name="gloss_alerts_gin"),
            # Trigram pour la recherche libre
            GinIndex(fields=["search_text"], name="gloss_search_trgm", opclasses=["gin_trgm_ops"]),
            # Gouvernance & perf
            models.Index(fields=["is_active", "version"], name="idx_active_version"),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            # Index vectoriel (pgvector)
            models.Index(fields=["embedding"], opclasses=["vector_cosine_ops"], name="gloss_embedding_cosine"),
        ]
