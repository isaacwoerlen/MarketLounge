import json
from django.http import HttpResponse
from .models import GlossaryNode

def export_glossary_json(request):
    nodes = GlossaryNode.objects.all().order_by('path')
    data = []

    for node in nodes:
        entry = {
            "node_id": node.node_id,
            "glossary_id": node.glossary_id,
            "type": node.type,
            "parent_id": node.parent.node_id if node.parent else None,
            "path": node.path,
            "labels": {
                "fr": node.label_fr,
                "en": node.label_en or ""
            },
            "seo": {
                "keywords": {
                    "fr": node.seo_keywords_fr or [],
                    "en": node.seo_keywords_en or []
                },
                "description": {
                    "fr": node.seo_description_fr or "",
                    "en": node.seo_description_en or ""
                }
            },
            "embedding_ref": node.embedding_ref,
            "embedding_model": node.embedding_model,
            "embedding_dim": node.embedding_dim
        }

        # Ajout des champs spécifiques selon le type
        if node.type in ['metier', 'operation']:
            entry["definition"] = {
                "fr": node.definition_fr or "",
                "en": node.definition_en or ""
            }
        if node.type == 'operation':
            entry["procede"] = {
                "fr": node.procede_fr or "",
                "en": node.procede_en or ""
            }
        if node.type == 'variante':
            entry["explication_technique"] = {
                "fr": node.explication_technique_fr or "",
                "en": node.explication_technique_en or ""
            }

        data.append(entry)

    response = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="glossary_nodes.json"'
    return response
from django.shortcuts import render

# Create your views here.
