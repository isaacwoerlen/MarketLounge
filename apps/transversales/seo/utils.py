# apps/seo/utils.py
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import get_language
from .models import SEOBlock
from apps.language.utils import get_active_langs

def get_seo_for_object(obj, lang=None):
    if lang is None:
        lang_code = get_language()
        lang = get_active_langs().filter(code=lang_code).first()
    if not lang:
        return None
    content_type = ContentType.objects.get_for_model(obj)
    return SEOBlock.objects.filter(
        content_type=content_type,
        object_id=str(obj.pk),
        language=lang,
        is_active=True
    ).first()