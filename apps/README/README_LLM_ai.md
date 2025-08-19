README_LLM_ai
Objectif
L’app LLM_ai est transversale, centralisant les interactions avec les services IA externes (Mistral, OpenAI fallback, autres providers via admin) pour enrichissements sémantiques (traductions, résumés, suggestions, reranking). Utilisée par language, matching, glossary, dico, seo, elle expose une API interne sécurisée et est gérée via admin Django.
Fonctionnement

Providers : Mistral (principal), OpenAI (fallback), extensible via LLMConfig (ex. : Grok, Claude).
Configuration : LLMConfig (provider, api_key (encrypted), model, model_version, timeout, max_retries, tenant_id) via /admin/LLM_ai/llmconfig/.
Services : enrich_text (traductions, résumés), enrich_ranking (reranking), avec retries (backoff exponentiel, max 3), circuit-breaker (p95>500ms → fallback).
Tâches async : run_enrich_batch (Celery, llm_queue, batch_size=200).
API interne : /api/v1/llm/enrich/ (TokenAuthentication, 100 req/min).
Multilingue : Normalisation BCP-47 (language.utils.normalize_locale), détection langue optionnelle (langdetect), fallback traduction pour langues rares.
Monitoring : Métriques (llm.request_success, llm.request_latency_ms, llm.fallback_rate, llm.tokens_total, llm.cost_usd_total) via metrics.services, logs (transversales.LLM_ai).
Pipeline :graph TD
    A[App request: language/matching] --> B[Prétraitement: normalize, langdetect]
    B --> C[LLMConfig: select by tenant_id/default]
    C --> D[Mistral API]
    C --> E[OpenAI API (fallback)]
    D --> F[Enrich: text, ranking]
    E --> F
    F --> G[Celery: run_enrich_batch]
    G --> H[Response: enriched text/ranking]
    H --> I[Log: LLMRequestLog]


Erreur handling : Timeout (503), échec total (503, message="No provider available"), circuit-breaker (fallback_rate>10% → OpenAI).
Prompt safety : Gabarits versionnés, variables whitelisted, PII redacted, no data retention (Mistral/OpenAI opt-out).

Cas d’usage

Traductions : "usinage" → "milling" pour language.
Résumés : Concepts 100 mots pour dico.
Reranking : Améliore shortlists pour matching.

Intégration

Avec language : Traductions via enrich_text.
Avec matching : Reranking via enrich_ranking.
Avec verticales : glossary, dico, seo via LLMMixin or enrich_text.
Multi-tenancy : tenant_id dans LLMConfig, sélection tenant → default → 503.

Fichiers

Standards :
models.py : LLMConfig, LLMRequestLog (audit).
admin.py : Admin pour LLMConfig (staff-only, test connexion).
services.py : enrich_text, enrich_ranking.
tasks.py : run_enrich_batch (Celery, llm_queue).
views.py : API REST (/api/v1/llm/enrich/).
urls.py : Routes API.
apps.py : Configuration, checks.
serializers.py : Sérialisation LLMConfig, LLMRequestLog.


Tests :
tests/test_models.py : Validation LLMConfig, LLMRequestLog.
tests/test_services.py : Tests enrich_text, enrich_ranking.
tests/test_tasks.py : Tests Celery.
tests/test_views.py : Tests API.
tests/test_admin.py : Tests admin.
tests/test_integration.py : Tests flux complet.
tests/factories.py : Factories pour LLMConfig, LLMRequestLog.



Tests

Couverture : >80% (pytest --cov=transversales.LLM_ai).
Unitaires : Validation LLMConfig, services, tâches, API, admin.
Intégration : Flux language → LLM_ai → API.
Cas couverts :
Validation : Regex api_key, provider (mistral, openai).
Erreurs : Timeout (503), échec total (503), tenant mismatch.
Scalabilité : Batching (200), rate limiting (100/min).
Double-provider : Mistral down → OpenAI.


Commandes :pytest tests/ --cov=transversales.LLM_ai --cov-report=html



Déploiement

Dépendances : django-fernet-fields, requests, celery[redis], django-rest-framework, langdetect.
Docker Compose :services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    depends_on: [db, redis]
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
  redis:
    image: redis:6
  celery:
    build: .
    command: celery -A config worker -Q llm_queue -l info
    depends_on: [redis]


Settings :
MISTRAL_API_KEY, OPENAI_API_KEY.
LLM_QUOTA=1000 (req/jour/tenant).
LLM_RERANK_ENABLED=True.
LLM_RERANK_TIMEOUT_MS=500.


CI/CD : GitHub Actions (pytest, flake8).

Sécurité

Encryption : api_key encrypté (django-fernet-fields).
Permissions : Staff-only pour admin, TokenAuthentication pour API.
Quotas : LLM_QUOTA par tenant, 429 + Retry-After.
Prompt safety : Gabarits versionnés, variables whitelisted, PII redacted.
Audit : LLMRequestLog (tenant_id, timestamp, provider, tokens, cost).

API Exemples

POST /api/v1/llm/enrich :{
  "text": "usinage",
  "task": "translate",
  "prompt": "Translate to English",
  "lang": "fr",
  "tenant_id": "tenant_123",
  "config_id": null
}

Response :{
  "enriched_text": "milling",
  "provider": "mistral",
  "latency_ms": 200,
  "tokens": 10,
  "cost_usd": 0.001,
  "used_fallback": false
}


POST /api/v1/llm/rerank :{
  "query": "soudure inox",
  "items": [{"ref_id": "comp_1", "text": "Soudure inox 316L"}],
  "tenant_id": "tenant_123"
}

Response :{
  "results": [{"ref_id": "comp_1", "score": 0.95}],
  "provider": "mistral",
  "latency_ms": 300,
  "tokens": 20,
  "cost_usd": 0.002,
  "used_fallback": false
}



Notes

Admin Django : CRUD pour IA externes (ex. : ajouter Grok, modifier Mistral) via LLMConfig.
Scalabilité : Batching (200), rate limiting (100/min).
Extensibilité : Ajout providers via LLMConfig.
Monitoring : SLOs (p95<500ms, fallback_rate<10%).

Drop-in pour LLM_ai/models.py
Pour démarrer l’implémentation, voici models.py avec LLMConfig et LLMRequestLog, respectant les conventions de language.models.py et ta demande de gestion admin.

# apps/transversales/LLM_ai/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from fernet_fields import EncryptedCharField
import re
import logging

logger = logging.getLogger(name)
class LLMConfig(models.Model):    """    Configuration pour providers IA externes (Mistral, OpenAI, etc.).    Gérée via admin Django, supporte multi-tenancy.    """    provider = models.CharField(        max_length=50,        choices=(('mistral', 'Mistral'), ('openai', 'OpenAI'), ('grok', 'Grok')),        help_text=("IA provider")    )    api_key = EncryptedCharField(        max_length=255,        validators=[RegexValidator(            regex=r'^sk-[a-zA-Z0-9]+$',            message=("Invalid API key format")        )],        help_text=("Encrypted API key")    )    model = models.CharField(        max_length=100,        default="mistral-large-latest",        help_text=("Model name (e.g., mistral-large-latest)")    )    model_version = models.CharField(        max_length=50,        blank=True,        help_text=("Model version (e.g., v1.2)")    )    timeout = models.PositiveIntegerField(        default=500,        help_text=("Timeout in milliseconds")    )    max_retries = models.PositiveIntegerField(        default=3,        help_text=("Max retries for API calls")    )    tenant_id = models.CharField(        max_length=100,        blank=True,        validators=[RegexValidator(            regex=r'^tenant[a-zA-Z0-9_]+$',            message=("Invalid tenant_id format")        )],        help_text=("Tenant identifier (blank for default)")    )    created_at = models.DateTimeField(auto_now_add=True)    updated_at = models.DateTimeField(auto_now=True)
class Meta:
    unique_together = ('provider', 'tenant_id')
    indexes = [models.Index(fields=['tenant_id'])]

def clean(self):
    """Validation des champs."""
    if self.tenant_id and not self.tenant_id.startswith("tenant_"):
        logger.error(f"Invalid tenant_id for LLMConfig: {self.tenant_id}")
        raise ValidationError(_("Tenant_id must start with 'tenant_'"))
    super().clean()

def __str__(self):
    return f"{self.provider} ({self.tenant_id or 'default'})"

class LLMRequestLog(models.Model):    """    Log des requêtes LLM pour audit/traçabilité.    """    tenant_id = models.CharField(        max_length=100,        blank=True,        help_text=("Tenant identifier")    )    provider = models.CharField(        max_length=50,        help_text=("IA provider used")    )    task = models.CharField(        max_length=50,        help_text=("Task type (e.g., translate, rerank)")    )    latency_ms = models.PositiveIntegerField(        help_text=("Request latency in milliseconds")    )    tokens = models.PositiveIntegerField(        default=0,        help_text=("Tokens used")    )    cost_usd = models.DecimalField(        max_digits=10,        decimal_places=4,        default=0,        help_text=("Estimated cost in USD")    )    used_fallback = models.BooleanField(        default=False,        help_text=_("Whether fallback provider was used")    )    created_at = models.DateTimeField(auto_now_add=True)
class Meta:
    indexes = [models.Index(fields=['tenant_id', 'created_at'])]

def __str__(self):
    return f"{self.provider}: {self.task} ({self.created_at})"
