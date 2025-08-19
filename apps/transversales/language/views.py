# apps/transversales/language/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.decorators import action
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError
from .models import Language, TranslatableKey, Translation, TranslationJob
from .serializers import (
    LanguageSerializer, TranslatableKeySerializer, TranslationSerializer,
    TranslationCreateSerializer, TranslationReviewSerializer, TranslationJobSerializer
)
from .services import store_translation, compute_checksum
from .tasks import run_translation_job, run_vectorize_scopes
from .permissions import (
    can_view_language, can_change_language, can_view_translatable_key,
    can_change_translatable_key, can_view_translation, can_change_translation,
    can_view_translation_job, can_rerun_translation_job
)
import logging

logger = logging.getLogger(__name__)

class LanguagePermission(BasePermission):
    """Permission class for LanguageViewSet."""
    def has_permission(self, request, view):
        return can_view_language(request.user, None)

    def has_object_permission(self, request, view, obj):
        if request.method in ["PUT", "PATCH", "DELETE"]:
            return can_change_language(request.user, obj)
        return can_view_language(request.user, obj)

class TranslatableKeyPermission(BasePermission):
    """Permission class for TranslatableKeyViewSet."""
    def has_permission(self, request, view):
        return can_view_translatable_key(request.user, None)

    def has_object_permission(self, request, view, obj):
        if request.method in ["PUT", "PATCH", "DELETE"]:
            return can_change_translatable_key(request.user, obj)
        return can_view_translatable_key(request.user, obj)

class TranslationPermission(BasePermission):
    """Permission class for TranslationViewSet."""
    def has_permission(self, request, view):
        return can_view_translation(request.user, None)

    def has_object_permission(self, request, view, obj):
        if request.method in ["PUT", "PATCH"]:
            return can_change_translation(request.user, obj, selected_language=request.data.get("language_code"))
        return can_view_translation(request.user, obj)

class TranslationJobPermission(BasePermission):
    """Permission class for TranslationJobViewSet."""
    def has_permission(self, request, view):
        return can_view_translation_job(request.user, None)

    def has_object_permission(self, request, view, obj):
        if request.method in ["PUT", "PATCH", "DELETE"]:
            return can_rerun_translation_job(request.user, obj)
        return can_view_translation_job(request.user, obj)

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint pour consulter les langues actives.
    - Filtrage: code, is_default.
    - Permissions: Superusers/staff uniquement.
    - Auth: Token ou Session.
    """
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [LanguagePermission]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["code", "is_default"]

    def handle_exception(self, exc):
        """Personnalise les réponses d'erreur."""
        logger.error(f"Erreur LanguageViewSet pour user {self.request.user.username if self.request.user.is_authenticated else 'anonymous'}: {str(exc)}")
        if isinstance(exc, ValidationError):
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)

class TranslatableKeyViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les clés traduisibles.
    - Filtrage: scope, tenant_id.
    - Permissions: Superusers, staff global, ou même tenant.
    - Auth: Token ou Session.
    """
    queryset = TranslatableKey.objects.all()
    serializer_class = TranslatableKeySerializer
    permission_classes = [TranslatableKeyPermission]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["scope", "tenant_id"]

    def handle_exception(self, exc):
        """Personnalise les réponses d'erreur."""
        logger.error(f"Erreur TranslatableKeyViewSet pour user {self.request.user.username if self.request.user.is_authenticated else 'anonymous'}: {str(exc)}")
        if isinstance(exc, ValidationError):
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)

class TranslationViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les traductions.
    - Filtrage: language__code, tenant_id, key__scope.
    - Actions: create, review.
    - Permissions: Superusers, staff global, ou même tenant.
    - Auth: Token ou Session.
    """
    queryset = Translation.objects.all()
    serializer_class = TranslationSerializer
    permission_classes = [TranslationPermission]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["language__code", "tenant_id", "key__scope"]

    def get_serializer_class(self):
        """Utilise TranslationCreateSerializer pour création."""
        if self.action == "create":
            return TranslationCreateSerializer
        if self.action == "review":
            return TranslationReviewSerializer
        return TranslationSerializer

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """
        Revoit une traduction (nouvelle version si modifiée).
        - Valide via TranslationReviewSerializer.
        - Crée nouvelle version si texte changé.
        - Retourne détails de la traduction mise à jour.
        """
        translation = self.get_object()
        serializer = TranslationReviewSerializer(translation, data=request.data, context={"request": request})
        if not serializer.is_valid():
            logger.error(f"Erreur revue traduction {translation.id} par {request.user.username}: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            updated_translation = serializer.save()
            logger.info(f"Revue traduction {translation.id} par {request.user.username}, nouvelle version: {updated_translation.version}")
            return Response(TranslationSerializer(updated_translation).data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erreur revue traduction {translation.id} par {request.user.username}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def handle_exception(self, exc):
        """Personnalise les réponses d'erreur."""
        logger.error(f"Erreur TranslationViewSet pour user {self.request.user.username if self.request.user.is_authenticated else 'anonymous'}: {str(exc)}")
        if isinstance(exc, ValidationError):
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)

class TranslationJobViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les jobs de traduction.
    - Filtrage: state, source_locale, tenant_id.
    - Actions: create (lance job async), vectorize.
    - Permissions: Superusers, staff global.
    - Auth: Token ou Session.
    """
    queryset = TranslationJob.objects.all()
    serializer_class = TranslationJobSerializer
    permission_classes = [TranslationJobPermission]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["state", "source_locale", "tenant_id"]

    def create(self, request, *args, **kwargs):
        """
        Crée un job de traduction et le lance via Celery.
        - Valide les données et enregistre en état 'queued'.
        - Retourne les détails du job avec task ID.
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Erreur création job par {request.user.username}: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            job = serializer.save(state="queued")
            task = run_translation_job.delay(job.id)
            response_data = self.get_serializer(job).data
            response_data["task_id"] = task.id
            logger.info(f"Job de traduction {job.id} créé par {request.user.username}, Task ID: {task.id}")
            return Response(response_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error(f"Erreur création job par {request.user.username}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def vectorize(self, request, pk=None):
        """
        Déclenche la vectorisation asynchrone des traductions d'un job.
        - Vérifie les permissions et lance via Celery.
        - Retourne confirmation avec scopes.
        """
        job = self.get_object()
        try:
            task = run_vectorize_scopes.delay(job.scope_filter, job.tenant_id)
            logger.info(f"Vectorisation job {job.id} lancée par {request.user.username}, Task ID: {task.id}")
            return Response(
                {"queued": True, "scopes": job.scope_filter, "task_id": task.id},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            logger.error(f"Erreur vectorisation job {job.id} par {request.user.username}: {str(e)}")
            return Response(
                {"error": f"Échec vectorisation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def handle_exception(self, exc):
        """Personnalise les réponses d'erreur."""
        logger.error(f"Erreur TranslationJobViewSet pour user {self.request.user.username if self.request.user.is_authenticated else 'anonymous'}: {str(exc)}")
        if isinstance(exc, ValidationError):
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)