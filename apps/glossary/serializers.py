# apps/glossary/serializers.py
from rest_framework import serializers
from .models import GlossaryNode, GlossaryType

class GlossaryNodeSerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(
        slug_field='glossary_id',
        queryset=GlossaryNode.objects.all(),
        allow_null=True,
        required=False
    )
    parent_glossary_id = serializers.CharField(source='parent.glossary_id', read_only=True, allow_null=True)

    class Meta:
        model = GlossaryNode
        fields = [
            'glossary_id', 'node_id', 'type', 'parent', 'parent_glossary_id', 'path',
            'labels', 'definition', 'procede', 'explication_technique', 'seo',
            'embedding', 'is_active', 'version', 'alerts',
            'created_at', 'updated_at', 'created_by', 'reviewed_by', 'search_text'
        ]
        read_only_fields = ['path', 'created_at', 'updated_at', 'version', 'parent_glossary_id', 'search_text']

    def validate_labels(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Labels must be a dictionary.")
        if not value.get('fr') or not value.get('en'):
            raise serializers.ValidationError("Labels for 'fr' and 'en' are required.")
        return value

    def validate_seo(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("SEO must be a dictionary.")
        for lang, obj in value.items():
            if not isinstance(obj, dict):
                raise serializers.ValidationError(f"seo.{lang} must be a dictionary.")
            if 'keywords' in obj and not isinstance(obj['keywords'], list):
                raise serializers.ValidationError(f"seo.{lang}.keywords must be a list.")
            if 'description' in obj and not isinstance(obj['description'], str):
                raise serializers.ValidationError(f"seo.{lang}.description must be a string.")
        return value

    def validate_alerts(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Alerts must be a list.")
        for a in value:
            if not isinstance(a, dict) or 'type' not in a or 'detail' not in a:
                raise serializers.ValidationError("Each alert must be a dict with 'type' and 'detail'.")
        return value

    def validate(self, data):
        instance = self.instance or GlossaryNode()
        for key, value in data.items():
            setattr(instance, key, value)
        instance.full_clean()
        return data