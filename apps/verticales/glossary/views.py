# apps/glossary/views.py

from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_page
from django.contrib.admin.views.decorators import staff_member_required
from django.core import management

from .models import GlossaryNode


def _serialize_node(n: GlossaryNode, include_embedding: bool = False):
    data = {
        "glossary_id": n.glossary_id,
        "node_id": n.node_id,
        "type": n.type,
        "parent_glossary_id": n.parent.glossary_id if n.parent else None,
        "path": n.path,
        "labels": n.labels or {},
        "definition": n.definition or {},
        "procede": n.procede or {},
        "explication_technique": n.explication_technique or {},
        "seo": n.seo or {},
        "is_active": n.is_active,
        "version": n.version,
        "alerts": n.alerts or [],
        "created_at": n.created_at.isoformat(timespec="seconds") if n.created_at else None,
        "updated_at": n.updated_at.isoformat(timespec="seconds") if n.updated_at else None,
    }
    if include_embedding:
        data["embedding"] = n.embedding
    return data


@require_GET
@cache_page(300)
def glossary_detail(request, glossary_id: str):
    try:
        node = GlossaryNode.objects.select_related("parent").get(glossary_id=glossary_id)
    except GlossaryNode.DoesNotExist:
        raise Http404("Glossary node not found")
    include_embedding = str(request.GET.get("include_embedding", "0")).lower() in {"1", "true", "yes"}
    return JsonResponse(
        _serialize_node(node, include_embedding=include_embedding),
        safe=False,
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )


@require_GET
def health(request):
    # Compte robuste des nœuds avec alerte 'ia_pending'
    pending_ia = GlossaryNode.objects.extra(
        where=["EXISTS (SELECT 1 FROM jsonb_array_elements(alerts) AS a WHERE a->>'type' = 'ia_pending')"]
    ).count()
    return JsonResponse({
        "status": "ok",
        "total_nodes": GlossaryNode.objects.count(),
        "pending_ia_nodes": pending_ia,
    })


@require_POST
@staff_member_required
def generate_glossary_node(request, glossary_id: str):
    try:
        GlossaryNode.objects.get(glossary_id=glossary_id)
    except GlossaryNode.DoesNotExist:
        raise Http404("Glossary node not found")

    try:
        management.call_command("generate_glossary", glossary_id=glossary_id)
        return JsonResponse(
            {"status": "success", "glossary_id": glossary_id, "message": f"IA generation triggered for {glossary_id}"}
        )
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
