# utils_core/alerts.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import re

try:  # Django-friendly mais optionnel
    from django.core.exceptions import ValidationError
except Exception:  # pragma: no cover
    class ValidationError(Exception):  # type: ignore
        pass

__all__ = ["format_alert", "validate_alerts", "merge_alerts"]

# ──────────────────────────────────────────────────────────────────────────────
# Normalisation
# ──────────────────────────────────────────────────────────────────────────────

# Autorisés pour type/field : a-z0-9._- (lower)
_RE_SAFE_KEY = re.compile(r"[^a-z0-9._-]")
_RE_MULTI_US  = re.compile(r"_+")

def _norm_key(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    v = str(val).strip().lower()
    v = _RE_SAFE_KEY.sub("_", v)
    v = _RE_MULTI_US.sub("_", v).strip("_")
    return v[:64] if v else None

def _truncate(msg: str, limit: Optional[int]) -> str:
    if not limit or len(msg) <= limit:
        return msg
    # coupe proprement et ajoute une ellipse
    return (msg[: max(0, limit - 1)] + "…") if limit >= 2 else msg[:limit]

# ──────────────────────────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────────────────────────

def format_alert(
    alert: Mapping[str, Any],
    *,
    allowed_types: Optional[Iterable[str]] = None,
    default_field: Optional[str] = None,
    truncate_message: Optional[int] = 512,
    keep_extra: bool = False,
) -> Dict[str, Any]:
    """
    Normalise une alerte {type, field?, message} :
      - type/field → lower + [a-z0-9._-]
      - field optionnel : fallback sur default_field
      - message : strip + éventuel truncation
      - allowed_types : si fourni, valide l'appartenance
      - keep_extra : conserve les clés supplémentaires “as-is”
    Retourne un dict propre, prêt à sérialiser/logguer.
    """
    if not isinstance(alert, Mapping):
        raise ValidationError("Alert must be a mapping")
    
    typ = _norm_key(alert.get("type", "generic")) or "generic"
    if allowed_types and typ not in allowed_types:
        raise ValidationError(f"Alert type '{typ}' not in allowed_types")
    
    msg = str(alert.get("message", "")).strip() or "Alert"
    msg = _truncate(msg, truncate_message)
    
    out: Dict[str, Any] = {"type": typ, "message": msg}
    
    fld = _norm_key(alert.get("field", default_field))
    if fld:
        out["field"] = fld
    
    if keep_extra:
        for k, v in alert.items():
            if k not in ("type", "field", "message"):
                out[k] = v
    
    return out

def validate_alerts(
    alerts: Iterable[Mapping[str, Any]],
    *,
    allowed_types: Optional[Iterable[str]] = None,
    truncate_message: Optional[int] = 512,
    strict: bool = True,
    keep_extra: bool = False,
) -> List[Dict[str, Any]]:
    """
    Valide et normalise une liste d'alertes.
    - strict=True → lève ValidationError si une alerte est invalide
    - strict=False → ignore les alertes invalides
    """
    out: List[Dict[str, Any]] = []
    for a in alerts:
        try:
            out.append(
                format_alert(
                    a,
                    allowed_types=allowed_types,
                    truncate_message=truncate_message,
                    keep_extra=keep_extra,
                )
            )
        except ValidationError:
            if strict:
                raise
    return out

def merge_alerts(
    alerts_lists: Iterable[Iterable[Mapping[str, Any]]],
    *,
    dedupe_on: str = "type_field",
    prefer: str = "last",
    allowed_types: Optional[Iterable[str]] = None,
    truncate_message: Optional[int] = 512,
    keep_extra: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fusionne plusieurs listes d'alertes en retirant les doublons.
    - Utilisé dans errors.AlertException pour dédupliquer automatiquement les alertes.
    - Utilisé dans language pour SEO alerts (validate_seo_lengths), curation pour validations,
      et LLM_ai pour erreurs structurées.

    Args:
        alerts_lists: Liste de listes d'alertes.
        dedupe_on:
            * "type_field"          → un seul message par couple (type, field)
            * "type_field_message"  → dédupe uniquement si message identique aussi
        prefer:
            * "longer"  → conserve l’alerte avec le message le plus long
            * "first"   → conserve la première rencontrée
            * "last"    → conserve la dernière rencontrée
        allowed_types: Types d'alertes autorisés.
        truncate_message: Limite de taille des messages.
        keep_extra: Conserve les champs supplémentaires.

    Returns:
        List[Dict[str, Any]]: Liste d'alertes fusionnées et triées.

    Examples:
        >>> from utils_core.alerts import merge_alerts
        >>> alerts = [[{"type": "seo", "field": "title", "message": "Too long"}],
        ...           [{"type": "seo", "field": "title", "message": "Too long"}]]
        >>> merge_alerts(alerts, dedupe_on="type_field_message", prefer="last")
        [{"type": "seo", "field": "title", "message": "Too long"}]  # language: SEO alerts
        >>> merge_alerts([[{"type": "validation", "field": "concept", "message": "Invalid"}]], prefer="first")
        [{"type": "validation", "field": "concept", "message": "Invalid"}]  # curation: validation
    """
    key_mode = dedupe_on
    if key_mode not in ("type_field", "type_field_message"):
        raise ValidationError("dedupe_on must be 'type_field' or 'type_field_message'")
    if prefer not in ("longer", "first", "last"):
        raise ValidationError("prefer must be 'longer', 'first' or 'last'")

    merged: Dict[Tuple[str, Optional[str], Optional[str]], Dict[str, Any]] = {}

    def _make_key(a: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str]]:
        t = a.get("type", "")
        f = a.get("field")
        m = a.get("message", "")
        return (t, f, m if key_mode == "type_field_message" else None)

    # normalise puis fusionne
    for lst in alerts_lists:
        if not lst:
            continue
        normalized = validate_alerts(
            lst,
            allowed_types=allowed_types,
            truncate_message=truncate_message,
            strict=False,
            keep_extra=keep_extra,
        )
        for a in normalized:
            k = _make_key(a)
            if k not in merged:
                merged[k] = a
            else:
                if prefer == "first":
                    continue
                if prefer == "last":
                    merged[k] = a
                elif prefer == "longer":
                    if len(a.get("message", "")) > len(merged[k].get("message", "")):
                        merged[k] = a

    # tri final
    out = list(merged.values())
    out.sort(key=lambda d: (d.get("type", ""), d.get("field", ""), d.get("message", "")))
    return out
    