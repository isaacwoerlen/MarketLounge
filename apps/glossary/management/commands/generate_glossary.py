# apps/glossary/management/commands/generate_glossary.py
import json
import re
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from apps.glossary.models import GlossaryNode
from sentence_transformers import SentenceTransformer
import logging

# Configurer le logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Generate glossary fields via IA for a given glossary_id or all nodes with ia_pending alerts"

    def add_arguments(self, parser):
        parser.add_argument('glossary_id', type=str, nargs='?', help='Glossary ID of the node to process (optional)')
        parser.add_argument('--all-pending', action='store_true', help='Process all nodes with ia_pending alerts')

    def handle(self, *args, **kwargs):
        glossary_id = kwargs.get('glossary_id')
        all_pending = kwargs.get('all_pending')

        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {e}")
            raise CommandError(f"Failed to load IA model: {e}")

        if all_pending:
            nodes = GlossaryNode.objects.filter(
                Q(alerts__contains=[{'type': 'ia_pending'}]) | Q(labels={})
            ).select_related('parent')
        elif glossary_id:
            try:
                nodes = [GlossaryNode.objects.get(glossary_id=glossary_id)]
            except GlossaryNode.DoesNotExist:
                logger.error(f"Node with glossary_id {glossary_id} not found")
                raise CommandError(f"Node {glossary_id} not found")
        else:
            raise CommandError("Specify either a glossary_id or use --all-pending")

        processed = 0
        errors = 0
        for node in nodes:
            try:
                with transaction.atomic():
                    self.process_node(node, model)
                processed += 1
                logger.info(f"Successfully processed node {node.glossary_id}")
                self.stdout.write(self.style.SUCCESS(f"Processed {node.glossary_id}"))
            except Exception as e:
                logger.error(f"Error processing node {node.glossary_id}: {e}")
                errors += 1
                node.alerts = node.alerts or []
                node.alerts.append({
                    'type': 'ia_error',
                    'detail': f"Failed to process: {str(e)}"
                })
                node.save(update_fields=['alerts'])
                self.stdout.write(self.style.ERROR(f"Error processing {node.glossary_id}: {e}"))

        summary = f"Processed {processed} node(s), {errors} error(s)"
        if errors:
            logger.warning(summary)
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def process_node(self, node, model):
        term = node.labels.get('fr', node.node_id)
        logger.info(f"Processing term: {term} for node {node.glossary_id}")

        prompt = (
            'Tu es un expert industriel. Analyse le terme : "{term}". '
            'Dis-moi s’il s’agit d’un métier, d’une opération ou d’une variante. '
            'Si ce n’est pas un métier, indique son métier parent (glossary_id). '
            'Donne aussi une description claire et concise. '
            'Format JSON : '
            '{"type": "...", "parent": "...", "description": "...", '
            '"labels": {"fr": "...", "en": "..."}, "explication_technique": "..."}'
        ).format(term=term)

        try:
            embedding = model.encode(term, convert_to_tensor=False).tolist()

            # Appel LLM (exemple avec transformers ; remplacez par votre modèle)
            from transformers import pipeline
            nlp = pipeline('text-generation', model='gpt2')  # À remplacer
            response = nlp(prompt, max_length=200)[0]['generated_text']
            # Extraction JSON robuste
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                ia_response = json.loads(json_match.group(0))
            else:
                raise ValueError("No valid JSON in LLM response")

            node.type = ia_response['type']
            if ia_response['parent']:
                try:
                    node.parent = GlossaryNode.objects.get(glossary_id=ia_response['parent'])
                except GlossaryNode.DoesNotExist:
                    node.alerts = node.alerts or []
                    node.alerts.append({
                        'type': 'parent_not_found',
                        'detail': f"Parent {ia_response['parent']} not found"
                    })
            node.labels = ia_response['labels']
            node.definition = {
                lang: ia_response['description']
                for lang in ['fr', 'en']
                if node.type in ['metier', 'operation']
            }
            node.procede = {
                lang: ia_response['description']
                for lang in ['fr', 'en']
                if node.type == 'operation'
            }
            node.explication_technique = {
                lang: ia_response['explication_technique']
                for lang in ['fr', 'en']
                if node.type == 'variante'
            }
            node.seo = {
                lang: {'keywords': [term.lower()], 'description': ia_response['description']}
                for lang in ['fr', 'en']
            }
            node.embedding = embedding
            node.alerts = node.alerts or []
            node.alerts = [a for a in node.alerts if a['type'] != 'ia_pending']
            node.alerts.append({
                'type': 'ia_processed',
                'detail': 'Fields updated by IA'
            })
            node.created_by = node.created_by or get_user_model().objects.get_or_create(
                username='bot',
                defaults={'is_active': False}
            )[0]

            if hasattr(node, 'search_text'):
                node.search_text = " ".join([
                    node.labels.get(lang, "") for lang in ("fr", "en", "de", "it")
                ] + [
                    " ".join(node.seo.get(lang, {}).get("keywords", [])) for lang in ("fr", "en", "de", "it")
                ])

            node.full_clean()  # Valider règles métier
            node.save()
            logger.info(f"Updated node {node.glossary_id} with IA-generated fields")

        except Exception as e:
            node.alerts = node.alerts or []
            node.alerts.append({
                'type': 'ia_error',
                'detail': f"Invalid JSON or processing error: {str(e)}"
            })
            node.save(update_fields=['alerts'])
            raise