# apps/language/permissions.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from typing import Union, Optional
from .models import Language, TranslatableKey, Translation, TranslationJob
import logging

logger = logging.getLogger(__name__)

UserType = Union[AbstractBaseUser, AnonymousUser]

# Configuration
STAFF_GLOBAL = getattr(settings, "LANGUAGE_STAFF_GLOBAL", True)
TENANT_ID_VALIDATOR = RegexValidator(
    regex=r'^tenant_[a-zA-Z0-9_]+$',
    message="Invalid tenant_id format. Must start with 'tenant_' and contain only alphanumeric characters or underscores."
)

def _get_obj_tenant_id(obj: Union[Language, TranslatableKey, Translation, TranslationJob]) -> Optional[str]:
    """
    Extract tenant_id from object (TranslatableKey, Translation, TranslationJob).
    Returns None for Language (global resource) or if tenant_id is absent/invalid.
    """
    try:
        if isinstance(obj, Language):
            return None  # Language is global, no tenant_id
        if isinstance(obj, (TranslatableKey, TranslationJob)):
            tenant_id = getattr(obj, "tenant_id", None)
            if tenant_id:
                TENANT_ID_VALIDATOR(tenant_id)
            return tenant_id
        if isinstance(obj, Translation) and hasattr(obj, "key"):
            tenant_id = getattr(obj.key, "tenant_id", None)
            if tenant_id:
                TENANT_ID_VALIDATOR(tenant_id)
            return tenant_id
        return None
    except ValidationError as e:
        logger.warning(f"Invalid tenant_id for object {obj.__class__.__name__} (id: {getattr(obj, 'id', 'unknown')}): {str(e)}")
        return None

def _is_same_tenant(user: UserType, obj: Union[Language, TranslatableKey, Translation, TranslationJob], 
                    tenant_id: Optional[str] = None) -> bool:
    """
    Check if user belongs to the same tenant as the object or provided tenant_id.
    Returns True for superusers/staff with STAFF_GLOBAL, or if tenant_ids match.
    Assumes User model has tenant_id attribute (string or None). If absent, falls back to None.
    """
    if not user.is_authenticated:
        logger.warning(f"Access denied: Anonymous user attempted to access {obj.__class__.__name__} (id: {getattr(obj, 'id', 'unknown')})")
        return False
    if user.is_superuser or (user.is_staff and STAFF_GLOBAL):
        return True
    obj_tenant_id = _get_obj_tenant_id(obj)
    check_tenant_id = tenant_id or obj_tenant_id
    if not check_tenant_id:
        logger.warning(f"Access denied: No tenant_id for {obj.__class__.__name__} (id: {getattr(obj, 'id', 'unknown')})")
        return False
    try:
        # Assume User has tenant_id; fallback to None if attribute missing
        user_tenant_id = getattr(user, "tenant_id", None)
        if user_tenant_id:
            TENANT_ID_VALIDATOR(user_tenant_id)
        if user_tenant_id != check_tenant_id:
            logger.warning(f"Access denied: Tenant mismatch for user {user.username} (user_tenant: {user_tenant_id}, obj_tenant: {check_tenant_id})")
            return False
        return True
    except ValidationError as e:
        logger.warning(f"Access denied: Invalid user tenant_id for {user.username}: {str(e)}")
        return False

def can_view_language(user: UserType, language: Language) -> bool:
    """
    Check if user can view a Language (global resource).
    Allowed: Authenticated superusers, staff.
    """
    allowed = user.is_authenticated and (user.is_superuser or user.is_staff)
    if not allowed:
        logger.warning(f"View language denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {language.id})")
    return allowed

def can_change_language(user: UserType, language: Language) -> bool:
    """
    Check if user can change a Language (global resource).
    Allowed: Superusers, staff.
    """
    allowed = user.is_authenticated and (user.is_superuser or user.is_staff)
    if not allowed:
        logger.warning(f"Change language denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {language.id})")
    return allowed

def can_delete_language(user: UserType, language: Language) -> bool:
    """
    Vérifie si l'utilisateur peut supprimer une langue (sauf langue par défaut, admin/staff).
    """
    allowed = user.is_authenticated and (user.is_superuser or (user.is_staff and not getattr(language, "is_default", False)))
    if not allowed:
        logger.warning(f"Delete language denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {language.id}, is_default: {language.is_default})")
    return allowed

def can_view_translatable_key(user: UserType, key: TranslatableKey, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut voir une clé traduisible (tenant-specific).
    """
    allowed = user.is_superuser or (user.is_staff and STAFF_GLOBAL) or _is_same_tenant(user, key, tenant_id)
    if not allowed:
        logger.warning(f"View translatable key denied for user {user.username if user.is_authenticated else 'anonymous'} (key: {key.scope}:{key.key}, tenant: {tenant_id or key.tenant_id})")
    return allowed

def can_change_translatable_key(user: UserType, key: TranslatableKey, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut modifier une clé traduisible (tenant-specific).
    """
    allowed = user.is_superuser or (user.is_staff and STAFF_GLOBAL) or _is_same_tenant(user, key, tenant_id)
    if not allowed:
        logger.warning(f"Change translatable key denied for user {user.username if user.is_authenticated else 'anonymous'} (key: {key.scope}:{key.key}, tenant: {tenant_id or key.tenant_id})")
    return allowed

def can_view_translation(user: UserType, translation: Translation, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut voir une traduction (tenant-specific).
    """
    allowed = user.is_superuser or (user.is_staff and STAFF_GLOBAL) or _is_same_tenant(user, translation, tenant_id)
    if not allowed:
        logger.warning(f"View translation denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {translation.id}, tenant: {tenant_id or translation.key.tenant_id})")
    return allowed

def can_change_translation(user: UserType, translation: Translation, tenant_id: str | None = None, selected_language: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut modifier une traduction (tenant-specific, langue choisie).
    """
    if user.is_superuser or (user.is_staff and STAFF_GLOBAL):
        return True
    if not _is_same_tenant(user, translation, tenant_id):
        logger.warning(f"Change translation denied for user {user.username} (id: {translation.id}, tenant: {tenant_id or translation.key.tenant_id})")
        return False
    # Restriction UX : édition dans la langue choisie (ou user.language, ou langue par défaut)
    user_language = selected_language or getattr(user, "language", None) or Language.get_default_lang().code
    if not Language.objects.filter(code=user_language, is_active=True).exists():
        logger.warning(f"Change translation denied for user {user.username}: invalid language {user_language}")
        return False
    allowed = translation.language.code == user_language
    if not allowed:
        logger.warning(f"Change translation denied for user {user.username} (id: {translation.id}, language: {translation.language.code}, requested: {user_language})")
    return allowed

def can_view_translation_job(user: UserType, job: TranslationJob, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut voir un job de traduction (admin/staff uniquement).
    """
    allowed = user.is_authenticated and (user.is_superuser or user.is_staff)
    if not allowed:
        logger.warning(f"View translation job denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {job.id})")
    return allowed

def can_rerun_translation_job(user: UserType, job: TranslationJob, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut relancer un job (admin/staff uniquement, non running).
    """
    allowed = (user.is_authenticated and (user.is_superuser or user.is_staff) and job.state != "running")
    if not allowed:
        logger.warning(f"Rerun translation job denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {job.id}, state: {job.state})")
    return allowed

def can_export_translation_job(user: UserType, job: TranslationJob, tenant_id: str | None = None) -> bool:
    """
    Vérifie si l'utilisateur peut exporter un job (admin/staff uniquement).
    """
    allowed = user.is_authenticated and (user.is_superuser or user.is_staff)
    if not allowed:
        logger.warning(f"Export translation job denied for user {user.username if user.is_authenticated else 'anonymous'} (id: {job.id})")
    return allowed
    