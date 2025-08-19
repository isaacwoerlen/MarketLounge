# apps/transversales/language/urls.py
from django.urls import path, include
from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.permissions import IsAdminUser
from rest_framework.throttling import UserRateThrottle
from .views import LanguageViewSet, TranslatableKeyViewSet, TranslationViewSet, TranslationJobViewSet
import logging

logger = logging.getLogger(__name__)

# Throttling léger pour usage interne
class LanguageThrottle(UserRateThrottle):
    rate = '200/minute'  # 200 requêtes/minute pour admins internes

# Router DRF avec trailing slash
router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'keys', TranslatableKeyViewSet, basename='key')
router.register(r'translations', TranslationViewSet, basename='translation')
router.register(r'jobs', TranslationJobViewSet, basename='job')

app_name = 'language'

# Endpoints activés uniquement si LANG_ENABLE_API=True
if getattr(settings, 'LANG_ENABLE_API', False):
    urlpatterns = [
        path('api/v1/language/', include(router.urls)),  # Versioning avec préfixe
        # Actions personnalisées pour jobs (usage interne, sécurisé)
        path('api/v1/language/jobs/<pk>/run/', TranslationJobViewSet.as_view({
            'post': 'create'
        }, permission_classes=[IsAdminUser], throttle_classes=[LanguageThrottle]), name='job-run'),
        path('api/v1/language/jobs/<pk>/export/', TranslationJobViewSet.as_view({
            'post': 'export_results'
        }, permission_classes=[IsAdminUser], throttle_classes=[LanguageThrottle]), name='job-export'),
    ]
else:
    urlpatterns = []  # Désactive endpoints si non activé

# Note: Pour documentation OpenAPI future (V1.1+), intégrer drf-spectacular
# Exemple: router.register avec schema_name pour générer specs