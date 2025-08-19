# apps/glossary/management/commands/generate_glossary.py

import os
import json
import re
import logging
import requests
from typing import Dict, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
from sklearn.metrics.pairwise import cosine_similarity

from apps.glossary.models import GlossaryNode, GlossaryType
from apps.language.utils import get_active_langs

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
MISTRAL_TIMEOUT = 20  # seconds
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large")
MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")


def _extract_first_json_block(text: str) -> Dict[str, Any]:
    """
    Extrait le premier bloc JSON valide d'un texte (réponse IA).
    """
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No valid JSON found in model response.")
    return json.loads(m.group(0))


def _normalize_type(t: Optional[str]) -> Optional[str]:
    if not t:
        return None
    t = t.strip().lower()
    mapping = {
        "metier": GlossaryType.METIER,
        "métier": GlossaryType.METIER,
        "operation": GlossaryType.OPERATION,
        "opération": GlossaryType.OPERATION,
        "variante": GlossaryType.VARIANTE,
    }
    return mapping.get(t)


class Command(BaseCommand):
    help = "Enrichit les nœuds du glossaire via IA (Mistral) + embeddings (SentenceTransformers)."

    def add_arguments(self, parser):
        parser.add_argument("glossary_id", type=str, nargs="?", help="glossary_id à traiter (optionnel)")
        parser.add_argument("--all-pending", action="store_true", help="Traiter tous les nœuds en attente IA")
        parser.add_argument("--dry-run", action="store_true", help="Ne pas enregistrer, affiche un résumé")

    def handle(self, *args, **kwargs):
        glossary_id = kwargs.get("glossary_id")
        all_pending = kwargs.get("all_pending")
        dry_run = kwargs.get("dry_run")

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise CommandError("MISTRAL_API_KEY manquant dans l'environnement.")

        # Chargement embedding model
        try:
            emb_model = SentenceTransformer(EMBEDDING_MODEL)
        except Exception as e:
            logger.exception("Failed to load sentence-transformers model")
            raise CommandError(f"Embedding model load error: {e}")

        # Sélection des nœuds à traiter
        if all_pending:
            # Robuste: chercher les nœuds avec alerte 'ia_pending' OU labels vides
            nodes = (
                GlossaryNode.objects.extra(
                    where=[
                        "alerts IS NOT NULL AND EXISTS (SELECT 1 FROM jsonb_array_elements(alerts) AS a WHERE a->>'type' = 'ia_pending')"
                    ]
                )
                | GlossaryNode.objects.filter(Q(labels={}) | Q(labels__isnull=True))
            ).select_related("parent").distinct()
        elif glossary_id:
            try:
                nodes = [GlossaryNode.objects.select_related("parent").get(glossary_id=glossary_id)]
            except GlossaryNode.DoesNotExist:
                raise CommandError(f"Node {glossary_id} not found")
        else:
            raise CommandError("Spécifie un glossary_id ou --all-pending")

        processed = 0
        errors = 0
        updated_ids = []
        errored_ids = []

        for node in nodes:
            try:
                changes = self.process_node(node, emb_model, api_key, dry_run=dry_run)
                processed += 1
                if changes:
                    updated_ids.append(node.glossary_id)
            except Exception as e:
                errors += 1
                errored_ids.append(node.glossary_id)
                logger.exception("Error processing node %s: %s", node.glossary_id, e)
                # Tenter d'étiqueter l'erreur sur le nœud
                try:
                    node.alerts = (node.alerts or []) + [{"type": "ia_error", "detail": str(e)}]
                    if not dry_run:
                        node.save(update_fields=["alerts", "updated_at"])
                except Exception:
                    pass

        summary = f"Processed {processed} node(s), {errors} error(s)"
        self.stdout.write(self.style.WARNING(summary) if errors else self.style.SUCCESS(summary))
        if updated_ids:
            self.stdout.write(self.style.SUCCESS(f"Updated: {', '.join(updated_ids[:10])} {'...' if len(updated_ids)>10 else ''}"))
        if errored_ids:
            self.stdout.write(self.style.WARNING(f"Errored: {', '.join(errored_ids[:10])} {'...' if len(errored_ids)>10 else ''}"))

    # ---------- Traitement d'un nœud ----------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def process_node(self, node: GlossaryNode, emb_model: SentenceTransformer, api_key: str, dry_run: bool = False) -> bool:
        """
        Retourne True si des champs ont changé et ont été persistés (hors dry-run).
        """
        term = (node.labels or {}).get("fr") or (node.labels or {}).get("en") or node.node_id

        # 1) Génération IA (Mistral)
        ia = self._call_mistral(term, api_key)

        # 2) Normalisation/validation des champs IA
        new_type = _normalize_type(ia.get("type"))
        if new_type:
            node.type = new_type  # laisser 'clean()' valider hiérarchie ensuite

        parent_ref = ia.get("parent")
        if parent_ref:
            try:
                parent = GlossaryNode.objects.get(glossary_id=parent_ref)
                node.parent = parent
            except GlossaryNode.DoesNotExist:
                node.alerts = (node.alerts or []) + [
                    {"type": "parent_not_found", "detail": f"Parent {parent_ref} not found"}
                ]

        labels = ia.get("labels") or {}
        description = ia.get("description") or {}
        exptech = ia.get("explication_technique") or {}

        # Remplissage des champs selon le type (stratégie Pilier 1)
        # - metier/operation : definition
        # - operation : procede en bonus si fourni
        # - variante : explication_technique
        node.labels = labels or node.labels or {}
        if node.type in (GlossaryType.METIER, GlossaryType.OPERATION):
            node.definition = description or node.definition or {}
        if node.type == GlossaryType.OPERATION:
            node.procede = (ia.get("procede") or description or node.procede or {})
        if node.type == GlossaryType.VARIANTE:
            node.explication_technique = exptech or node.explication_technique or {}

        # SEO basique
        node.seo = {
            lang: {
                "keywords": [str(term).lower()],
                "description": (node.definition or {}).get(lang, "") if isinstance(node.definition, dict) else "",
            }
            for lang in ACTIVE_LANGS
        }

        # 3) Embedding
        try:
            vec = emb_model.encode(str(term), convert_to_numpy=True).tolist()
            node.embedding = vec  # champs VectorField(dim=384)
        except Exception as e:
            node.alerts = (node.alerts or []) + [{"type": "embedding_error", "detail": str(e)}]

        # 4) Alertes qualité
        if node.type == GlossaryType.VARIANTE and not node.parent:
            node.alerts = (node.alerts or []) + [{"type": "missing_parent", "detail": "Variante sans parent"}]

        if not any((node.labels or {}).get(lang) for lang in ACTIVE_LANGS):
            node.alerts = (node.alerts or []) + [{"type": "missing_labels", "detail": "Aucun label renseigné"}]

        if node.type in (GlossaryType.METIER, GlossaryType.OPERATION):
            if not any((node.definition or {}).get(lang) for lang in ACTIVE_LANGS):
                node.alerts = (node.alerts or []) + [{"type": "missing_description", "detail": "Description vide"}]

        # Similarité parent/enfant
        try:
            if node.parent and node.parent.embedding:
                sim = float(cosine_similarity([node.embedding], [node.parent.embedding])[0][0])
                if sim < SIMILARITY_THRESHOLD:
                    node.alerts = (node.alerts or []) + [
                        {"type": "low_similarity", "detail": f"Similarité faible avec parent : {sim:.2f}"}
                    ]
        except Exception as e:
            node.alerts = (node.alerts or []) + [{"type": "similarity_error", "detail": str(e)}]

        # Nettoyage d'alertes : retirer ia_pending si présent, marquer traité
        node.alerts = [a for a in (node.alerts or []) if a.get("type") != "ia_pending"]
        node.alerts.append({"type": "ia_processed", "detail": "Champs enrichis par IA"})

        # created_by automatique si manquant
        if not node.created_by_id:
            bot, _ = get_user_model().objects.get_or_create(username="bot", defaults={"is_active": False})
            node.created_by = bot

        # 5) Persistance avec les règles du modèle (recalcul node_id/path/search_text, propagation path)
        if dry_run:
            return True

        with transaction.atomic():
            node.full_clean()  # applique hiérarchie/publication
            node.save()        # déclenche recomputes + propagation éventuelle

        return True

    def _call_mistral(self, term: str, api_key: str) -> Dict[str, Any]:
        """
        Appel Mistral avec prompt Pilier 1 (type/parent/labels/description/explication_technique).
        """
        prompt = f"""
Tu es un expert industriel. Analyse le terme : "{term}".
Dis-moi s’il s’agit d’un métier, d’une opération ou d’une variante.
Si ce n’est pas un métier, indique son métier parent (glossary_id).
Donne une description claire en {', '.join(ACTIVE_LANGS)}.
Donne aussi une explication technique si c’est une variante.
Réponds STRICTEMENT au format JSON suivant :
{{
  "type": "...",
  "parent": "...",
  "labels": {{ {', '.join(f'"{lang}": "..."' for lang in ACTIVE_LANGS)} }},
  "description": {{ {', '.join(f'"{lang}": "..."' for lang in ACTIVE_LANGS)} }},
  "explication_technique": {{ {', '.join(f'"{lang}": "..."' for lang in ACTIVE_LANGS)} }}
}}
""".strip()

        try:
            r = requests.post(
                MISTRAL_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.2,
                },
                timeout=MISTRAL_TIMEOUT,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _extract_first_json_block(content)
        except Exception as e:
            raise CommandError(f"Mistral API error: {e}")
