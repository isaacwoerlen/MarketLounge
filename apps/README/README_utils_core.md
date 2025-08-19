utils_core README


🧱 Structure modulaire de utils_core (1 fichier = 1 rôle)



📁 Fichier
🎯 Rôle unique et clair
🔧 Fonctions / Contenu principal
📦 Utilisé par ≥ 3 apps



utils.py
Fonctions utilitaires génériques (non métier)
compute_checksum (idempotence), retry_on_exception (robustesse), slugify (URL-safe), Timer (latence), normalize_text, log_metric (ré-exports)
✅ Oui


validators.py
Validation et normalisation de champs métier/techniques
validate_lang, normalize_locale (BCP-47), validate_tenant_id, validate_scope, validate_checksum, validate_json_field
✅ Oui


text_cleaning.py
Pré-traitement et nettoyage de texte pour queries/traductions
normalize_text (queries in matching, source_text in language, prompts in LLM_ai), remove_accents, strip_html, standardize_whitespace
✅ Oui


metrics.py
Standardisation des métriques et observabilité
log_metric, format_tags, record_metric_wrapper (latency/success/error avec tags dynamiques)
✅ Oui


alerts.py
Validation et manipulation des alertes structurées
validate_alerts, format_alert, merge_alerts (intégré avec errors.AlertException)
✅ Oui


json_utils.py
Fonctions robustes pour manipuler du JSON
safe_json_loads, safe_json_dumps, extract_json_field
✅ Oui


env.py
Accès sécurisé aux variables d’environnement et config
get_env_variable (settings comme EMBEDDING_DIM, LLM_TIMEOUT), load_env_config, is_env_valid
✅ Oui


constants.py
Centralisation des constantes partagées (regex, lang codes, scopes, métriques)
LANG_CODES, REGEX_PATTERNS, DEFAULT_SCOPES, ALERT_TYPES, METRIC_MATCH_*
✅ Oui


types.py
Définition des types partagés (TypedDict, dataclasses, etc.)
Alert, Payload, MetricTags, TenantInfo, MatchFilters, TranslationJobPayload
✅ Oui


errors.py
Gestion des erreurs génériques et structurées
AppError, ValidationError, RetryableError, AlertException (avec merge_alerts)
✅ Oui


time_utils.py
Utilitaires pour gestion du temps et timestamps
utc_now, timestamp_ms, format_duration, parse_iso8601
✅ Oui


logging_utils.py
Configuration et gestion des logs structurés
setup_logging, get_logger, log_with_tags, log_exception
✅ Oui



📦 Utilisation
Chaque app (language, matching, curation, market, etc.) peut importer uniquement les modules nécessaires :
from utils_core.utils import compute_checksum, retry_on_exception, slugify, Timer  # Utilitaires génériques
from utils_core.validators import normalize_locale, validate_lang  # Normalisation/validation BCP-47
from utils_core.text_cleaning import normalize_text  # Queries, source_text, prompts
from utils_core.metrics import log_metric, record_metric_wrapper  # Monitoring latency/success
from utils_core.types import MatchFilters, TranslationJobPayload  # Typage
from utils_core.env import get_env_variable  # Settings partagés
from utils_core.alerts import validate_alerts, merge_alerts  # Alertes SEO/validations
from utils_core.errors import AlertException  # Erreurs avec alertes

Exemples par App
Language
from utils_core.utils import compute_checksum, Timer
from utils_core.validators import normalize_locale, validate_lang
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper
from utils_core.env import get_env_variable

# Normaliser et valider une langue
lang = normalize_locale("pt_BR")  # -> 'pt-br'
validate_lang(lang)

# Calculer checksum pour Translation.source_checksum
checksum = compute_checksum("Soudure inox 316L")

# Normaliser texte avant traduction
source_text = normalize_text("<p>Café français</p>", remove_accents_flag=True)

# Mesurer latence traduction
with Timer() as t:
    batch_translate_scope("seo:title", "fr", ["en"])
print(f"Translation took {t.elapsed_ms}ms")

# Instrumenter une tâche de traduction
@record_metric_wrapper('lang.batch_translate', static_tags={'operation': 'batch'})
def batch_translate_scope(scope, source_lang, target_langs): ...

# Récupérer config partagée
batch_size = get_env_variable("LANG_BATCH_SIZE", cast="int", default=200)

Matching
from utils_core.utils import retry_on_exception, slugify, Timer
from utils_core.validators import validate_tenant_id, normalize_locale
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper, METRIC_MATCH_DIRTY_RATIO
from utils_core.types import MatchFilters

# Valider tenant_id et normaliser query
validate_tenant_id("tenant_123")
query = normalize_text("Soudure Inox 316L aéronautique", remove_accents_flag=True)

# Générer un slug pour un identifiant
slug = slugify("Soudure Inox")  # -> 'soudure-inox'

# Mesurer latence encodage
with Timer() as t:
    encode_texts(["Soudure"], "fr")
print(f"Encoding took {t.elapsed_ms}ms")

# Instrumenter une recherche hybride
@record_metric_wrapper('match.hybrid_search', static_tags={'scope': 'company'},
                       dynamic_tags=lambda: {'tenant_id': get_current_tenant()})
def hybrid_search(query, tenant_id, scope): ...

# Monitorer le dirty ratio
log_metric(METRIC_MATCH_DIRTY_RATIO, 0.05, tags={'tenant_id': 'tenant_123', 'scope': 'company'})

# Typage des filtres
filters: MatchFilters = {"sector": "aeronautique", "region": "nord"}

Curation
from utils_core.utils import slugify
from utils_core.validators import validate_scope
from utils_core.alerts import validate_alerts, merge_alerts
from utils_core.errors import AlertException

# Valider un scope
validate_scope("seo:title")

# Générer un slug pour validation
slug = slugify("Concept Validation")  # -> 'concept-validation'

# Valider et fusionner des alertes de validation
alerts = validate_alerts([{"type": "validation", "field": "concept", "message": "Invalid"}])
merged = merge_alerts([alerts], dedupe_on="type_field_message", prefer="last")

# Lever une erreur avec alertes
raise AlertException("Validation failed", alerts=[{"type": "validation", "field": "concept", "message": "Invalid"}])

LLM_ai
from utils_core.utils import retry_on_exception, Timer
from utils_core.text_cleaning import normalize_text
from utils_core.env import get_env_variable

# Normaliser un prompt
prompt = normalize_text("Summarize this text", remove_accents_flag=True)

# Réessayer un appel LLM
@retry_on_exception(exception_types=(LLMError, TimeoutError), max_attempts=3)
def enrich_text(text): ...

# Mesurer latence appel LLM
with Timer() as t:
    enrich_text("Summary")
print(f"LLM call took {t.elapsed_ms}ms")

# Récupérer timeout LLM
timeout = get_env_variable("LLM_TIMEOUT", cast="float", default=5.0)

Métriques Attendues
Liste des métriques standardisées exportées via constants.py et metrics.py pour monitoring :

match.query.latency_ms: Latence des recherches hybrides (matching).
match.vector.hits: Nombre de hits vectoriels (matching).
match.index.dirty_ratio: Taux de désynchronisation des index (matching).
match.index_latency_ms: Latence d'indexation (matching).
match.recall_k: Rappel à k pour évaluation des recherches (matching).
match.faiss_hit_rate: Taux de hits FAISS (matching).
match.fusion_component_share: Poids des composants dans fusion (matching).
lang.bulk.latency_ms: Latence des traductions batch (language).
lang.cache.hit: Hits cache pour langues actives/défaut (language).
lang.cache.miss: Miss cache pour langues actives/défaut (language).


🧪 Tests
Les tests unitaires sont regroupés dans tests/test_utils_core/, avec un fichier par module :

test_utils.py
test_validators.py
test_text_cleaning.py
test_env.py
test_metrics.py
test_alerts.py
test_integration.py (tests intégrés mockant language/matching)
etc.

Tests intégrés dans test_integration.py simulent les usages dans les apps :

language: Translation.source_checksum, normalize_locale
matching: normalize_text pour queries, record_metric_wrapper
curation: validate_alerts, AlertException
LLM_ai: retry_on_exception, get_env_variable


📌 Bonnes pratiques

Ne pas inclure de logique métier dans utils_core.
Ajouter une fonction uniquement si elle est utilisée par ≥ 2 apps.
Documenter chaque ajout dans ce README.
Préférer l’ajout d’un nouveau fichier plutôt que de mélanger les rôles.


🛠️ Maintenance
Les migrations de fonctions depuis les apps vers utils_core doivent être :

Documentées dans MIGRATIONS.md
Ex. : compute_checksum migré depuis language/services.py pour centraliser SHA256 (idempotence embeddings/traductions).
Ex. : normalize_locale migré depuis language/services.py pour centraliser normalisation BCP-47 (language, matching, LLM_ai).
Ex. : retry_on_exception ajouté pour centraliser retries robustes (language tasks, matching encodage, LLM_ai appels).


Accompagnées de tests unitaires
Refactorées dans les apps via core_imports.py ou alias temporaires

