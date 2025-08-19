# apps/transversales/language/serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Language, TranslatableKey, Translation, TranslationJob
from .services import compute_checksum, get_active_language
from .utils import normalize_locale
import logging

logger = logging.getLogger(__name__)

class LanguageSerializer(serializers.ModelSerializer):
    """
    Serializer pour Language.
    """
    class Meta:
        model = Language
        fields = ["id", "code", "name", "is_active", "is_default", "priority"]
        read_only_fields = ["created_at", "updated_at"]

class TranslatableKeySerializer(serializers.ModelSerializer):
    """
    Serializer pour TranslatableKey.
    """
    class Meta:
        model = TranslatableKey
        fields = ["id", "scope", "key", "checksum", "is_blocking", "prompt_template", "tenant_id"]
        read_only_fields = ["checksum", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Valide l'unicité de scope+key+tenant_id.
        """
        scope = attrs.get("scope")
        key = attrs.get("key")
        tenant_id = attrs.get("tenant_id")
        if scope and key:
            qs = TranslatableKey.objects.filter(scope=scope, key=key, tenant_id=tenant_id)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                logger.warning(f"Clé existante: {scope}:{key}, tenant={tenant_id or 'N/A'}")
                raise ValidationError(_("A key with this scope and tenant already exists."))
        # Validation JSON pour prompt_template
        prompt_template = attrs.get("prompt_template", {})
        if not isinstance(prompt_template, dict):
            logger.warning(f"prompt_template invalide pour {scope}:{key}: doit être un dictionnaire")
            raise ValidationError(_("prompt_template must be a dictionary"))
        return attrs

class TranslationSerializer(serializers.ModelSerializer):
    """
    Serializer pour Translation (lecture).
    """
    language_code = serializers.CharField(source="language.code", read_only=True)
    key_scope = serializers.CharField(source="key.scope", read_only=True)
    key_name = serializers.CharField(source="key.key", read_only=True)
    has_embedding = serializers.SerializerMethodField()

    class Meta:
        model = Translation
        fields = [
            "id",
            "key",
            "key_scope",
            "key_name",
            "language",
            "language_code",
            "text",
            "version",
            "alerts",
            "has_embedding",
            "source_checksum",
            "origin",
            "provider_info",
            "domain",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["version", "alerts", "source_checksum", "provider_info", "created_at", "updated_at"]
        depth = 1  # Inclut champs nested (ex. : key.scope, language.code)

    def get_has_embedding(self, obj):
        """
        Vérifie si la traduction a un embedding.
        """
        return obj.embedding is not None

    def validate_alerts(self, value):
        """
        Valide le format JSON de alerts (liste de dicts avec type, field, message).
        """
        if not isinstance(value, list) or any(not isinstance(a, dict) or not all(k in a for k in ["type", "field", "message"]) for a in value):
            logger.warning(f"alerts invalide pour Translation ID {self.instance.id if self.instance else 'new'}: doit être une liste de dicts")
            raise ValidationError(_("alerts must be a list of dictionaries with type, field, message"))
        return value

class TranslationCreateSerializer(serializers.Serializer):
    """
    Serializer pour créer une Translation.
    """
    key = serializers.PrimaryKeyRelatedField(queryset=TranslatableKey.objects.all())
    target_lang = serializers.CharField(max_length=10)
    translated_text = serializers.CharField(allow_blank=True)
    source_text = serializers.CharField(allow_blank=True)

    def validate_target_lang(self, value):
        """
        Valide que la langue cible est active.
        """
        try:
            normalized = normalize_locale(value)
            return get_active_language(normalized).code
        except ValidationError as e:
            logger.warning(f"Langue cible invalide: {value}")
            raise serializers.ValidationError(str(e))

    def validate(self, attrs):
        """
        Valide l'ensemble des données.
        """
        key = attrs.get("key")
        target_lang = attrs.get("target_lang")
        translated_text = attrs.get("translated_text")
        source_text = attrs.get("source_text")
        if not translated_text and not source_text:
            logger.warning(f"Données invalides pour Translation: texte source et traduit absents")
            raise serializers.ValidationError(_("At least one of source_text or translated_text must be provided"))
        # Validation JSON pour alerts (si fourni via contexte)
        alerts = self.context.get("alerts", [])
        if not isinstance(alerts, list) or any(not isinstance(a, dict) or not all(k in a for k in ["type", "field", "message"]) for a in alerts):
            logger.warning(f"alerts invalide pour Translation {key}:{target_lang}: doit être une liste de dicts")
            raise ValidationError(_("alerts must be a list of dictionaries with type, field, message"))
        return attrs

    def create(self, validated_data):
        """
        Crée une nouvelle traduction.
        """
        try:
            key = validated_data["key"]
            target_lang = validated_data["target_lang"]
            translated_text = validated_data["translated_text"]
            source_text = validated_data["source_text"]

            from .services import store_translation
            store_translation(
                key=key,
                target_lang=target_lang,
                translated_text=translated_text,
                source_text=source_text,
                source_checksum=compute_checksum(source_text),
                origin="human",
                field="text",
                tenant_id=key.tenant_id,
                alerts=self.context.get("alerts", [])
            )
            return Translation.objects.get(key=key, language__code=target_lang)
        except Exception as e:
            logger.error(f"Erreur création traduction {key}:{target_lang}: {str(e)}")
            raise serializers.ValidationError(str(e))

    def update(self, instance, validated_data):
        """
        Met à jour une traduction (nouvelle version).
        """
        try:
            version = instance.version + 1
            new_translation = Translation(
                key=instance.key,
                language=instance.language,
                text=validated_data["translated_text"],
                version=version,
                alerts=self.context.get("alerts", instance.alerts),
                source_checksum=compute_checksum(validated_data["translated_text"]),
                origin="human",
                provider_info={},
            )
            new_translation.full_clean()
            new_translation.save()
            logger.info(f"Nouvelle version de traduction créée: {instance.key}:{instance.language}, version={version}")
            return new_translation
        except Exception as e:
            logger.error(f"Erreur mise à jour traduction {instance.key}:{instance.language}: {str(e)}")
            raise serializers.ValidationError(str(e))

class TranslationJobSerializer(serializers.ModelSerializer):
    """
    Serializer pour TranslationJob.
    """
    class Meta:
        model = TranslationJob
        fields = [
            "id",
            "name",
            "state",
            "source_locale",
            "target_locales",
            "scope_filter",
            "stats",
            "errors",
            "glossary_ids",
            "tenant_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["state", "stats", "errors", "created_at", "updated_at"]
        depth = 1  # Inclut champs nested si applicable

    def validate_source_locale(self, value):
        """
        Valide que la langue source est active.
        """
        try:
            normalized = normalize_locale(value)
            get_active_language(normalized)
            return normalized
        except ValidationError as e:
            logger.warning(f"Langue source invalide: {value}")
            raise serializers.ValidationError(str(e))

    def validate_target_locales(self, value):
        """
        Valide que les langues cibles sont actives, non dupliquées, et différentes de source.
        """
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            logger.warning("target_locales doit être une liste de chaînes")
            raise serializers.ValidationError(_("target_locales must be a list of strings"))
        normalized = [normalize_locale(x) for x in value]
        unique = list(dict.fromkeys(normalized))  # Déduplique
        if len(unique) < len(normalized):
            duplicates = [x for x in set(normalized) if normalized.count(x) > 1]
            logger.warning(f"Doublons dans target_locales: {duplicates}")
            raise serializers.ValidationError(f"Duplicate locales: {duplicates}")
        src = normalize_locale(self.initial_data.get("source_locale", ""))
        for lang in unique:
            try:
                get_active_language(lang)
                if lang == src:
                    logger.warning(f"Langue source {src} incluse dans target_locales")
                    raise serializers.ValidationError(f"Source locale {src} cannot be in target locales")
            except ValidationError as e:
                logger.warning(f"Langue cible invalide: {lang}")
                raise serializers.ValidationError(str(e))
        return unique

    def validate(self, attrs):
        """
        Valide l'ensemble des données.
        """
        stats = attrs.get("stats", {})
        errors = attrs.get("errors", [])
        if not isinstance(stats, dict):
            logger.warning(f"stats invalide pour TranslationJob {attrs.get('name', 'unknown')}: doit être un dictionnaire")
            raise ValidationError(_("stats must be a dictionary"))
        if not isinstance(errors, list):
            logger.warning(f"errors invalide pour TranslationJob {attrs.get('name', 'unknown')}: doit être une liste")
            raise ValidationError(_("errors must be a list"))
        return attrs
