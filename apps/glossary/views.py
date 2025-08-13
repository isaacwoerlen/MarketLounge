# apps/glossary/views.py
import json
from django.http import JsonResponse, Http404, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_page
from django.utils.timezone import is_naive, make_naive
from django.core import management
from django.db.models import Q
from .models import GlossaryNode, GlossaryType

def _iso(dt):
    if not dt:
        return None
    return (dt if is_naive(dt) else make_naive(dt)).isoformat(timespec="seconds")

def _serialize_node(n: GlossaryNode):
    return {
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
        "embedding": n.embedding,
        "is_active": n.is_active,
        "version": n.version,
        "alerts": n.alerts or [],
        "created_at": _iso(n.created_at),
        "updated_at": _iso(n.updated_at),
    }

def _apply_filters(qs, request):
    active_param = request.GET.get("active")
    if active_param and str(active_param).lower() in {"1", "true", "yes"}:
        qs = qs.filter(is_active=True)
    req_types = request.GET.getlist("type")
    if req_types:
        valid = {c for c, _ in GlossaryType.choices}
        qs = qs.filter(type__in=[t for t in req_types if t in valid])
    mv = request.GET.get("min_version")
    if mv:
        try:
            qs = qs.filter(version__gte=int(mv))
        except ValueError:
            pass
    alert_type = request.GET.get("alert_type")
    if alert_type:
        qs = qs.filter(alerts__contains=[{"type": alert_type}])
    search_term = request.GET.get("search")
    if search_term:
        qs = qs.filter(search_text__icontains=search_term)
    return qs

@require_GET
@cache_page(3600)
def export_glossary_json(request):
    qs = GlossaryNode.objects.all().select_related("parent")
    if request.GET.get("defer_embedding"):
        qs = qs.defer("embedding")
    qs = qs.order_by("path")
    qs = _apply_filters(qs, request)

    after = request.GET.get("after")
    if after:
        qs = qs.filter(path__gt=after)

    limit = int(request.GET.get("limit", 1000))
    qs = qs[:limit]

    def stream_json():
        yield "[\n"
        for i, node in enumerate(qs):
            if i > 0:
                yield ",\n"
            yield json.dumps(_serialize_node(node), ensure_ascii=False, indent=2)
        yield "\n]"

    response = StreamingHttpResponse(
        stream_json(),
        content_type="application/json; charset=utf-8"
    )
    response["Content-Disposition"] = 'attachment; filename="glossary_export.json"'
    return response

@require_GET
@cache_page(3600)
def glossary_detail(request, glossary_id: str):
    try:
        node = GlossaryNode.objects.select_related("parent").get(glossary_id=glossary_id)
    except GlossaryNode.DoesNotExist:
        raise Http404("Glossary node not found")
    return JsonResponse(
        _serialize_node(node),
        safe=False,
        json_dumps_params={"ensure_ascii": False, "indent": 2}
    )

@require_GET
def health(request):
    total_nodes = GlossaryNode.objects.count()
    pending_ia = GlossaryNode.objects.filter(alerts__contains=[{"type": "ia_pending"}]).count()
    return JsonResponse({
        "status": "ok",
        "total_nodes": total_nodes,
        "pending_ia_nodes": pending_ia
    })

@require_POST
def generate_glossary_node(request, glossary_id: str):
    try:
        node = GlossaryNode.objects.get(glossary_id=glossary_id)
        management.call_command("generate_glossary", glossary_id)
        return JsonResponse({
            "status": "success",
            "glossary_id": glossary_id,
            "message": f"IA generation triggered for {glossary_id}"
        })
    except GlossaryNode.DoesNotExist:
        raise Http404("Glossary node not found")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)