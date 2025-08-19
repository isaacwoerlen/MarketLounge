# apps/transversales/faiss_pgvector/models.py
from pgvector.django import VectorField
from django.conf import settings
from django.db import models

class EmbeddingMixin(models.Model):
    embedding = VectorField(dim=settings.EMBEDDING_DIM, null=True, blank=True)

    class Meta:
        abstract = True