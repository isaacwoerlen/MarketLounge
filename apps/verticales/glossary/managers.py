# apps/glossary/managers.py
from django.conf import settings
from django.db import models

class SearchableQuerySet(models.QuerySet):
    def text_search(self, q: str):
        # MVP: trigram
        return self.filter(search_text__icontains=q)

class SearchableManager(models.Manager):
    def get_queryset(self): return SearchableQuerySet(self.model, using=self._db)
    #Demain (V02), tu changes l’interne de text_search() pour tsvector/ts_rank, l’API ne bouge pas.
    def text_search(self, q): return self.get_queryset().text_search(q)  

