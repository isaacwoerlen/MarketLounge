# apps/verticales/matching/tests/test_models.py
import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.conf import settings
from verticales.matching.models import EmbeddingItem
import numpy as np

@pytest.mark.django_db
class EmbeddingItemTests(TestCase):
    def setUp(self):
        self.valid_data = {
            'tenant_id': 'tenant_123',
            'scope': 'company',
            'ref_id': 'comp_1',
            'lang': 'fr',
            'model': 'sentence-transformers/paraphrase-multilingual',
            'dim': getattr(settings, 'EMBEDDING_DIM', 384),
            'checksum': 'a' * 64,  # Mock SHA256
            'vector': np.random.rand(384).tolist(),  # Mock vector
            'payload': {'sector': 'aeronautique'},
        }

    def test_valid_embedding_item(self):
        """Test creation with valid data."""
        item = EmbeddingItem.objects.create(**self.valid_data)
        self.assertEqual(item.tenant_id, 'tenant_123')
        self.assertEqual(item.lang, 'fr')
        self.assertEqual(item.checksum, 'a' * 64)

    def test_unique_constraint(self):
        """Test (tenant_id, scope, ref_id) uniqueness."""
        EmbeddingItem.objects.create(**self.valid_data)
        with self.assertRaises(ValidationError):
            duplicate = self.valid_data.copy()
            EmbeddingItem.objects.create(**duplicate)

    def test_invalid_lang(self):
        """Test invalid BCP-47 lang code."""
        invalid_data = self.valid_data.copy()
        invalid_data['lang'] = 'invalid'
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()

    def test_invalid_tenant_id(self):
        """Test invalid tenant_id format."""
        invalid_data = self.valid_data.copy()
        invalid_data['tenant_id'] = 'invalid_id'
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()

    def test_invalid_checksum(self):
        """Test invalid SHA256 checksum."""
        invalid_data = self.valid_data.copy()
        invalid_data['checksum'] = 'invalid'
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()

    def test_invalid_dim(self):
        """Test invalid dimension."""
        invalid_data = self.valid_data.copy()
        invalid_data['dim'] = 512  # Not 384 or 768
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()

    def test_payload_size_limit(self):
        """Test payload size limit (10KB)."""
        invalid_data = self.valid_data.copy()
        invalid_data['payload'] = {'data': 'x' * (10 * 1024 + 1)}  # >10KB
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()

    def test_lang_normalization(self):
        """Test lang normalization (e.g., pt_BR → pt-br)."""
        item = EmbeddingItem(**self.valid_data)
        item.lang = 'pt_BR'
        item.full_clean()
        item.save()
        self.assertEqual(item.lang, 'pt-br')

    def test_vector_l2_normalization(self):
        """Test L2 normalization of vector."""
        item = EmbeddingItem(**self.valid_data)
        vector_np = np.array(item.vector)
        norm_before = np.linalg.norm(vector_np)
        item.save()
        item.refresh_from_db()
        vector_np_after = np.array(item.vector)
        norm_after = np.linalg.norm(vector_np_after)
        self.assertAlmostEqual(norm_after, 1.0, places=6)  # Normalized to 1
        if norm_before != 0:
            self.assertTrue(np.allclose(vector_np_after, vector_np / norm_before))

    def test_invalid_model(self):
        """Test invalid embedding model."""
        invalid_data = self.valid_data.copy()
        invalid_data['model'] = 'invalid-model'
        with self.assertRaises(ValidationError):
            item = EmbeddingItem(**invalid_data)
            item.full_clean()