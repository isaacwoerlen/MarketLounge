# apps/glossary/serializers.py
from rest_framework import serializers
from .models import GlossaryNode
from apps.language.utils import get_active_langs


class GlossaryNodeSerializer(serializers.ModelSerializer):
    # Parent référencé par son glossary_id (slug)
    parent = serializers.SlugRelatedField(
        slug_field="glossary_id",
        queryset=GlossaryNode.objects.all(),
        allow_null=True,
        required=False,
    )
    parent_glossary_id = serializers.CharField(
        source="parent.glossary_id", read_only=True, allow_null=True
    )

    # Gouvernance : created_by auto=CurrentUser; reviewed_by non éditable ici
    created_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    reviewed_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GlossaryNode
        fields = [
            "glossary_id",
            "node_id",
            "type",
            "parent",
            "parent_glossary_id",
            "path",
            "labels",
            "definition",
            "procede",
            "explication_technique",
            "seo",
            "embedding",
            "is_active",
            "version",
            "alerts",
            "created_at",
            "updated_at",
            "created_by",
            "reviewed_by",
            "search_text",
        ]
        read_only_fields = [
            # IDs & dérivés
            "glossary_id",
            "path",
            "search_text",
            # Gouvernance / système
            "version",
            "created_at",
            "updated_at",
            "reviewed_by",
            "embedding",  # géré par pipeline interne
        ]

    # ---------- Validations helpers ----------
    def _validate_multilang_dict(self, value, field_name, required=False, require_any_lang=False):
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(f"{field_name} must be a dictionary.")
        if required and require_any_lang:
            # Exige au moins UNE langue renseignée parmi ACTIVE_LANGS
            if not any(value.get(lang) for lang in ACTIVE_LANGS):
                raise serializers.ValidationError(
                    f"{field_name} requires at least one of {', '.join(ACTIVE_LANGS)}."
                )
        return value

    # Assouplir : labels non obligatoires à la création (gouvernance/IA peuvent compléter)
    def validate_labels(self, value):
        # On n'exige pas de langue spécifique, mais on valide la structure
        return self._validate_multilang_dict(value, "labels", required=False)

    def validate_definition(self, value):
        return self._validate_multilang_dict(value, "definition", required=False)

    def validate_procede(self, value):
        return self._validate_multilang_dict(value, "procede", required=False)

    def validate_explication_technique(self, value):
        return self._validate_multilang_dict(value, "explication_technique", required=False)

    def validate_seo(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("seo must be a dictionary.")
        for lang in ACTIVE_LANGS:
            seo_lang = value.get(lang, {})
            if not isinstance(seo_lang, dict):
                raise serializers.ValidationError(f"seo.{lang} must be a dictionary.")
            if "keywords" in seo_lang and not isinstance(seo_lang["keywords"], list):
                raise serializers.ValidationError(f"seo.{lang}.keywords must be a list.")
            if "description" in seo_lang and not isinstance(seo_lang["description"], str):
                raise serializers.ValidationError(f"seo.{lang}.description must be a string.")
        return value

    def validate_alerts(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("alerts must be a list.")
        for a in value:
            if not isinstance(a, dict) or "type" not in a or "detail" not in a:
                raise serializers.ValidationError("each alert must be a dict with 'type' and 'detail'.")
        return value

    # ---------- Validation globale ----------
    def validate(self, data):
        """
        On applique la validation du modèle (full_clean) pour :
        - Règles hiérarchiques (metier/opération/variante)
        - Règles de publication (reviewed_by + version)
        """
        instance = self.instance or GlossaryNode()
        for key, value in data.items():
            setattr(instance, key, value)
        instance.full_clean()  # délégué aux règles du modèle
        return data
