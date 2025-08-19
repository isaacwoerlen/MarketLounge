# utils_core/errors.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Union
import traceback

# ── Compat Django (optionnel) ──────────────────────────────────────────────────
try:
    from django.core.exceptions import ValidationError as DjangoValidationError  # type: ignore
except Exception:  # pragma: no cover
    DjangoValidationError = None  # type: ignore

__all__ = ["AppError", "ValidationError", "RetryableError", "AlertException"]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
    """
    Conversion douce en structures JSON-compatibles.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _to_dict(v) for k, v in obj.items()}  # type: ignore[dict-item]
    if isinstance(obj, (list, tuple, set)):
        return [_to_dict(v) for v in obj]
    # fallback
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"

def _format_cause_chain(exc: BaseException) -> List[Dict[str, str]]:
    """
    Remonte la chaîne __cause__/__context__ en texte.
    """
    chain: List[Dict[str, str]] = []
    seen = set()
    cur: Optional[BaseException] = exc  # type: ignore[assignment]
    while cur and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(
            {
                "type": getattr(cur.__class__, "__name__", "Exception"),
                "message": str(cur),
            }
        )
        cur = cur.__cause__ or cur.__context__
    return chain

# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────

class AppError(Exception):
    """
    Base des erreurs métier (sérialisables).
    - message : texte humain
    - code : identifiant court (ex.: 'invalid_lang')
    - details : payload structuré (JSON-safe)
    - tags : dimensions utiles (tenant,...)
    """
    def __init__(
        self,
        message: str = "",
        code: Optional[str] = None,
        *,
        details: Optional[Mapping[str, Any]] = None,
        tags: Optional[Mapping[str, Any]] = None,
        http_status: Optional[int] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.code = code or "app_error"
        self.details: Dict[str, Any] = dict(details or {})
        self.tags = dict(tags or {})
        self.http_status = http_status or 400
        self.cause = cause
        if cause:
            self.details["cause"] = _format_cause_chain(cause)

    def as_dict(self) -> Dict[str, Any]:
        """
        Retourne une version sérialisable JSON de l'erreur.
        """
        return {
            "code": self.code,
            "message": str(self),
            "details": _to_dict(self.details),
            "tags": _to_dict(self.tags),
            "http_status": self.http_status,
        }
    
    to_dict = as_dict  # Alias pour harmonisation

class ValidationError(AppError):
    """
    Erreur de validation (champs, formats).
    """
    def __init__(
        self,
        message: str = "",
        code: Optional[str] = None,
        *,
        details: Optional[Mapping[str, Any]] = None,
        tags: Optional[Mapping[str, Any]] = None,
        http_status: Optional[int] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code or "validation_error",
            details=details,
            tags=tags,
            http_status=http_status or 422,
            cause=cause,
        )
        # Compat Django
        if DjangoValidationError and isinstance(self.cause, DjangoValidationError):
            self.details["django_validation"] = str(self.cause)

class RetryableError(AppError):
    """
    Erreur marquée comme réessayable (ex.: timeout, erreurs réseau).
    """
    def __init__(
        self,
        message: str = "",
        code: Optional[str] = None,
        *,
        details: Optional[Mapping[str, Any]] = None,
        tags: Optional[Mapping[str, Any]] = None,
        http_status: Optional[int] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code or "retryable_error",
            details=details,
            tags=tags,
            http_status=http_status or 503,
            cause=cause,
        )

    def is_retryable(self) -> bool:
        return True

class AlertException(AppError):
    """
    Erreur accompagnée d'alertes structurées (ex. SEO, qualité, validation métier).
    - alerts : liste d'alertes {type, field?, message, ...}
    - Utilise merge_alerts pour dédupliquer automatiquement les alertes.
    """
    def __init__(
        self,
        message: str = "",
        code: Optional[str] = "alerts",
        *,
        alerts: Optional[Iterable[Mapping[str, Any]]] = None,
        allowed_types: Optional[Iterable[str]] = None,
        details: Optional[Mapping[str, Any]] = None,
        tags: Optional[Mapping[str, Any]] = None,
        http_status: Optional[int] = 422,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=dict(details or {}),
            tags=tags,
            http_status=http_status,
            cause=cause,
        )
        try:
            # Import tardif pour éviter dépendance dure
            from utils_core.alerts import merge_alerts, validate_alerts  # type: ignore
            self.alerts: List[Dict[str, Any]] = merge_alerts(
                [validate_alerts(alerts or [], allowed_types=allowed_types, strict=False)],
                dedupe_on="type_field_message",
                prefer="last",
            )[0]
        except Exception:
            # Fallback permissif si alerts.py indisponible
            self.alerts = []
            for a in alerts or []:
                if not isinstance(a, Mapping):
                    continue
                typ = str(a.get("type", "")).strip().lower() or "generic"
                msg = str(a.get("message", "")).strip() or "alert"
                item: Dict[str, Any] = {"type": typ, "message": msg}
                fld = a.get("field")
                if fld:
                    item["field"] = str(fld).strip().lower()
                self.alerts.append(item)
        # Stocke dans details pour sérialisation
        self.details["alerts"] = self.alerts