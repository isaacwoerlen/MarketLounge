📘 README — App language
Ce fichier respecte les conventions de [README Brief Technique_V02.md](../README Brief Technique_V02.md). Il décrit l'objectif, le type, les composants, l'intégration, et les responsabilités de l'app language.
🧩 Type d’App
Type : TransversaleDescription : Service réutilisable pour la traduction multilingue, appelé via pull par les verticales (ex. : glossary, market). Fournit une gestion centralisée des langues, traductions automatiques via LLM, et vectorisation sémantique pour la recherche via l'app matching.
🎯 Objectif

Centralise la traduction automatique via LLM_ai (Mistral API) avec retries robustes.
Gère les langues actives et par défaut avec cache (TTL 60s).
Orchestre les jobs batch asynchrones (Celery) avec mode dry-run pour prévisualisation.
Supporte la scalabilité multi-tenancy (millions de traductions).
Intègre la vectorisation pour recherche sémantique (via matching).
Valide les contraintes SEO (longueur, placeholders) avec métriques de performance.

🧱 Modèles Principaux
🗂️ Language



Champ
Type
Description



code
CharField(10)
Code langue (ex. : fr, regex ^[a-z]{2}(-[a-z]{2})?$)


name
CharField(100)
Nom lisible (ex. : Français)


is_active
BooleanField
Active traduction (default: True)


is_default
BooleanField
Langue défaut (unique, default: False)


priority
IntegerField
Priorité batch (1=haute, default: 5)


created_at
DateTimeField
Auto-création


updated_at
DateTimeField
Auto-mise à jour



Contraintes : Unicité code ; une seule is_default=True ; langue par défaut active.
Index : is_active, priority.
Comportements : Normalisation code (lowercase, tiret) via save() ; cache via LanguageManager (TTL configurable via settings.LANG_CACHE_TTL).

🛡️ Endpoints Potentiels (Migration HTTP)

Actuellement commentés (LANG_ENABLE_API=False), mais prêts pour activation en V1.1+.
Exemple dans urls.py :
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TranslationJobViewSet

router = DefaultRouter()
router.register(r'jobs', TranslationJobViewSet)

urlpatterns = [
    path('api/v1/language/', include(router.urls)),  # Ex. : /api/v1/language/jobs/
]

Exemple de vue dans views.py (ViewSet avec permissions) :
from rest_framework import viewsets, permissions
from .models import TranslationJob
from .serializers import TranslationJobSerializer

class TranslationJobViewSet(viewsets.ModelViewSet):
    queryset = TranslationJob.objects.all()
    serializer_class = TranslationJobSerializer
    permission_classes = [permissions.IsAdminUser]  # Sécurisé
    throttle_classes = []  # Throttling léger (ex. : 200/min)

    def perform_create(self, serializer):
        # Logique custom : déclenche Celery task après création
        instance = serializer.save()
        run_batch_translation_job.delay(instance.id)  # Async via Celery

Exemple de requête POST à /api/v1/language/jobs/ :
{
    "name": "Batch Traduction Glossary",
    "source_locale": "fr",
    "target_locales": ["en", "es"],
    "scope_filter": ["glossary:*"],
    "tenant_id": "tenant_123"
}

Réponse : 201 Created avec stats initiales.


🗂️ TranslatableKey

Champ
Type
Description

scope
CharField(64)
Contexte (ex. : glossary, seo)

key
CharField(255)
Clé unique dans scope (ex. : label)

checksum
CharField(64)
Hash SHA256 scope:key (via signal)

is_blocking
BooleanField
Bloque publication si non traduit (default: False)

prompt_template
JSONField
Template pour LLM (default: {})

tenant_id
CharField(36)
Multi-tenancy (ex. : tenant_xxx, null=True, validé via regex)

created_at
DateTimeField
Auto-création

updated_at
DateTimeField
Auto-mise à jour


Contraintes : Unicité scope + key.
Index : scope, key, checksum, tenant_id.
Comportements : Validation tenant_id (regex ^tenant_[a-zA-Z0-9_]+$).

🗂️ Translation

Champ
Type
Description

key
ForeignKey
Clé traduite

language
ForeignKey
Langue cible

text
TextField
Texte traduit

version
IntegerField
Version (default: 1)

alerts
JSONField
Alertes SEO (ex. : [{"type": "seo_length", "message": "..."}])

embedding
VectorField
Vecteur sémantique (dim configurable via settings.LANG_EMBEDDING_DIM, default: 384)

source_checksum
CharField(64)
Hash texte source

origin
CharField(20)
Origine (human, llm, tm)

provider_info
JSONField
Info LLM (ex. : {"provider": "mistral"})

domain
CharField(32)
Contexte domaine (null=True)

created_at
DateTimeField
Auto-création

updated_at
DateTimeField
Auto-mise à jour


Contraintes : Unicité key, language, version ; version >= 1.
Index : language, key+language, updated_at, source_checksum, domain.
Comportements : Validation alerts (liste de dicts), provider_info (dict).

🗂️ TranslationJob

Champ
Type
Description

name
CharField(255)
Nom du job

state
CharField(20)
État (pending, running, done, failed)

source_locale
CharField(5)
Langue source

target_locales
JSONField
Langues cibles

scope_filter
JSONField
Scopes (ex. : ["homepage", "seo:*"])

stats
JSONField
Statistiques (ex. : {"processed": 100, "per_lang": {"fr": 50}})

errors
JSONField
Erreurs (liste de chaînes)

glossary_ids
JSONField
IDs items (ex. : glossary IDs)

tenant_id
CharField(36)
Multi-tenancy (ex. : tenant_xxx, null=True)

created_at
DateTimeField
Auto-création

updated_at
DateTimeField
Auto-mise à jour


Permissions : rerun_translationjob, export_translationjob.
Index : state, created_at, tenant_id.

🛠️ Composants Internes
🗄️ Fichiers Principaux

models.py : Définit modèles avec contraintes, index, cache (LanguageManager), et signaux pour checksums.
services.py : Logique métier (ex. : store_translation, batch_translate_items) avec retries LLM via tenacity.
tasks.py : Tâches Celery (run_batch_translation_items, run_batch_translation_scope, run_vectorize_scopes) avec validation et métriques.
signals.py : Automatismes pour cache TM et vectorisation async avec métriques.
admin.py : Interface admin avec actions (rerun_job, export_results), sécurisée (CSRF, permissions).
views.py : API REST (ViewSets) avec permissions, filtres étendus (ex. : origin, source_checksum), et error handling.
serializers.py : Validation/sérialisation API avec contraintes (ex. : unicité scope+key).
utils.py : Normalisation (normalize_locale), cache (get_active_langs), et traduction batch (translate_fields).
permissions.py : Permissions granulaires pour multi-tenancy (ex. : can_view_translation).
management/commands/sync_translations.py : CLI pour sync/async traductions avec dry-run.
static/language/language_admin.js : UX admin (normalisation code, warnings, spinner) avec ARIA et i18n.
static/language/language_admin.css : Styles admin responsifs avec namespace .language-admin.
fixtures/languages.json : Fixture pour langues initiales (fr, en, pt-br, es) avec priority.
templates/admin/language/translation_job.html : Template admin pour TranslationJob avec sanitisation XSS et responsivité.

🧪 Tests

Tests unitaires recommandés (non fournis) dans tests/ avec pytest :

test_models.py : Contraintes, cache LanguageManager, validation tenant_id.
test_services.py : store_translation, retries LLM, validation SEO.
test_admin.py : Actions rerun_job, export_results, permissions.
test_views.py : API REST, permissions, filtres.
test_commands.py : CLI sync_translations (dry-run, args).
test_js.py : JS language_admin.js avec Jest (normalisation, ARIA).


Couverture : Viser >80% pour services.py, models.py (pytest-cov).

Outils : Flake8, Ruff, Black pour linting ; Jest pour JS.


🧪 Intégration dans une App Verticale
Les verticales (ex. : glossary) appellent language via pull. Exemple dans glossary :
from transversales.language.services import batch_translate_items
from verticales.matching.services import encode_text

class Term(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    label = models.CharField(max_length=255)
    definition = models.TextField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        batch_translate_items(
            item_ids=[self.id],
            fields=["label", "definition"],
            source_lang="fr",
            target_langs=["en", "es"],
            tenant_id="tenant_123",
        )
        self.embedding = encode_text(self.definition)  # Via matching

🔧 Comportements Automatiques

Normalisation : Language.code (ex. : pt-BR → pt-br).
Cache : TTL 60s pour get_active_langs/get_default_lang ; TM 1h pour tm_lookup.
Checksum : Calculé via signaux pre_save pour TranslatableKey/Translation.
Vectorisation : Async via post_save sur Translation (Celery si settings.LANG_EMBED_SYNC=False).
Multi-tenancy : Validation tenant_id via regex ^tenant_[a-zA-Z0-9_]+$.
Idempotence : Skip si source_checksum inchangé dans store_translation.
Retries LLM : 3 tentatives avec backoff exponentiel pour translate_text.
Métriques : Enregistrement via metrics pour traductions, vectorisations, et erreurs.

🧬 Exemples de Payloads JSON

alerts : [{"type": "seo_length", "field": "title", "message": "Too long (65 chars)"}]
scope_filter : ["homepage", "seo:*"]
target_locales : ["fr", "de"]
stats : {"total_keys": 120, "translated": 85, "per_lang": {"fr": 40}, "origin_breakdown": {"llm": 80, "tm": 5}}
prompt_template : {"tone": "formal", "max_length": 100}
provider_info : {"provider": "mistral", "model": "large-latest"}

🧠 Intégration avec LLM_ai et Matching

- **LLM_ai** : Traductions via `transversales.LLM_ai.services.translate_text` avec retries (tenacity). Préparation des prompts dans `services.py`.
- **Matching** : Vectorisation via `verticales.matching.services.encode_text` pour `Translation.embedding` (VectorField, dimension configurable via `settings.LANG_EMBEDDING_DIM`, défaut 384). Déclenchée async par signal `post_save` (Celery si `settings.LANG_EMBED_SYNC=False`). Un index HNSW avec `vector_cosine_ops` (configurable via `settings.LANG_VECTOR_OPCLASS`) optimise les recherches sémantiques multilingues. Les embeddings doivent être normalisés (L2) avant stockage pour garantir la précision des recherches cosine.

🚀 Recommandations Scalabilité

Indexing : Index composés sur Translation(key, language), TranslatableKey(scope, key).
Sharding : Partition par tenant_id ou scope.
Batching : Wildcards (seo:*) et settings.LANG_BATCH_SIZE (défaut: 200).
Performance : Tester 10M+ traductions avec factory_boy.
Monitoring : Métriques via transversales.metrics (ex. : traductions par langue, erreurs LLM).
Cache : Redis recommandé pour TM et résultats runtime (cache hit >80%).

📛 Conventions Nomage

Champs : snake_case (ex. : source_locale).
Tâches Celery : run_batch_translation_*.
Commandes CLI : sync_translations.py.
Scopes : snake_case ou hiérarchique (ex. : seo:title).

🧪 Tests Recommandés

Modèles : Contraintes (unicité, version >= 1), cache LanguageManager.
Services : Idempotence store_translation, retries LLM, validation SEO.
Admin : Actions sécurisées (CSRF, permissions).
CLI : Dry-run, validation args.
JS : Normalisation code, ARIA avec Jest.

🧪 Conclusion
L'app language est robuste, scalable, et prête pour l'IA sémantique. Elle respecte les frontières du Brief V02, centralise les appels IA via LLM_ai, et intègre les verticales via pull. Prioriser les tests pour gros volumes/multi-tenancy et l'intégration Redis pour cache.