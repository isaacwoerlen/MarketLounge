# apps/<app_name>/tests/test_models.py
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.core.cache import cache

# Import du modèle et des factories
from <app_name>.models import <ModelName>
from <app_name>.tests.factories import <ModelName>Factory
from faiss_pgvector.embeddings import encode_text  # Pour IA/matching sémantique
from unittest.mock import patch

@pytest.mark.django_db
class Test<ModelName>:
    def setup_method(self):
        cache.clear()  # Nettoie le cache avant chaque test

    def test_model_creation(self):
        """Vérifie la création d'un objet avec des champs valides."""
        obj = <ModelName>Factory()  # Utilise factory_boy
        assert obj.pk is not None
        assert obj.<field> == <ModelName>Factory.<field>  # Vérifie un champ clé

    def test_field_validations(self):
        """Vérifie les validations de champs (e.g., non-vide, format)."""
        invalid_data = {
            '<field>': '',  # Champ obligatoire vide
            # Ajouter autres champs invalides selon modèle
        }
        obj = <ModelName>Factory.build(**invalid_data)  # build, pas save
        with pytest.raises(ValidationError, match=r".*field.*"):
            obj.full_clean()

    def test_unique_constraint(self):
        """Vérifie les contraintes d'unicité."""
        <ModelName>Factory(<unique_field>="value")
        with pytest.raises(IntegrityError, match=r".*uniq_.*"):
            <ModelName>Factory(<unique_field>="value")  # Doublon

    def test_check_constraint(self):
        """Vérifie les CheckConstraints (e.g., version__gte=1)."""
        invalid_data = {
            '<constrained_field>': <invalid_value>,  # e.g., version=-1
        }
        obj = <ModelName>Factory.build(**invalid_data)
        with pytest.raises(ValidationError, match=r".*<constraint_name>.*"):
            obj.full_clean()

    def test_manager_behavior(self):
        """Vérifie les méthodes custom du manager."""
        <ModelName>Factory(<filter_field>=True)  # e.g., is_active=True
        <ModelName>Factory(<filter_field>=False)
        result = <ModelName>.objects.<custom_method>()  # e.g., get_active()
        assert len(result) == 1
        assert result[0].<field> == <expected_value>

    def test_save_behavior(self):
        """Vérifie les comportements automatiques dans save() (e.g., normalisation)."""
        obj = <ModelName>Factory.build(<field>="<raw_value>")  # e.g., code="PT-br"
        obj.save()
        assert obj.<field> == "<normalized_value>"  # e.g., code="pt-br"

    def test_json_field_validation(self):
        """Vérifie les JSONFields (e.g., alerts, stats)."""
        invalid_data = {
            '<json_field>': "<invalid_format>",  # e.g., alerts="not_a_list"
        }
        obj = <ModelName>Factory.build(**invalid_data)
        with pytest.raises(ValidationError, match=r".*must be a.*"):
            obj.full_clean()

    @patch('faiss_pgvector.embeddings.encode_text')
    def test_embedding_generation(self, mock_encode_text):
        """Vérifie la génération d'embedding (si applicable)."""
        mock_encode_text.return_value = b"mocked_vector"
        obj = <ModelName>Factory(<text_field>="Test text")
        obj.save()
        assert obj.embedding == b"mocked_vector"
        mock_encode_text.assert_called_once_with("Test text")

    def test_cache_behavior(self):
        """Vérifie le cache du manager (si applicable)."""
        cache_key = f"<app_name>:<model_name>:custom_cache"
        <ModelName>Factory(<filter_field>=True)
        result = <ModelName>.objects.<custom_method>()  # e.g., get_active()
        cached_result = cache.get(cache_key)
        assert cached_result is not None
        assert len(cached_result) == len(result)

    def test_multi_tenant_isolation(self):
        """Vérifie l'isolation multi-tenant (si tenant_id présent)."""
        obj1 = <ModelName>Factory(tenant_id="tenant1")
        obj2 = <ModelName>Factory(tenant_id="tenant2")
        assert <ModelName>.objects.filter(tenant_id="tenant1").count() == 1
        assert obj1.tenant_id != obj2.tenant_id

    def test_signal_trigger(self):
        """Vérifie les signaux (e.g., post_save pour vectorisation)."""
        with patch('<app_name>.signals.<signal_handler>') as mock_signal:
            obj = <ModelName>Factory()
            mock_signal.assert_called_once_with(
                sender=<ModelName>,
                instance=obj,
                created=True,
                **{}
            )