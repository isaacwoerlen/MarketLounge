utils_core README

🧱 Structure modulaire de utils_core (1 fichier = 1 rôle)



📁 Fichier
🎯 Rôle unique et clair
🔧 Fonctions / Contenu principal
📦 Utilisé par ≥ 3 apps



utils.py
Fonctions utilitaires génériques (non métier)
compute_checksum (idempotence embeddings/traductions), retry_on_exception (robustesse appels LLM/tasks), normalize_text, log_metric, slugify, Timer
✅ Oui


validators.py
Validation et normalisation de champs métier/techniques
validate_lang, normalize_locale (BCP-47 for language/matching), validate_tenant_id, validate_scope, validate_checksum, validate_json_field
✅ Oui


text_cleaning.py
Pré-traitement et nettoyage de texte pour queries/traductions
normalize_text (queries in matching, source_text in language, prompts in LLM_ai), remove_accents, strip_html, standardize_whitespace
✅ Oui


metrics.py
Standardisation des métriques et observabilité
log_metric, format_tags, record_metric_wrapper (latency/success/error avec tags dynamiques, ex. : match.hybrid_search, lang.batch)
✅ Oui


alerts.py
Validation et manipulation des alertes structurées
validate_alerts, format_alert, merge_alerts (intégré avec errors.AlertException, ex. : SEO dans language, validations dans curation)
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
Centralisation des constantes partagées (regex, lang codes, scopes, etc.)
LANG_CODES, REGEX_PATTERNS, DEFAULT_SCOPES, ALERT_TYPES, METRIC_MATCH_DIRTY_RATIO
✅ Oui


types.py
Définition des types partagés (TypedDict, dataclasses, etc.)
Alert, Payload, MetricTags, TenantInfo, MatchFilters (matching filters), TranslationJobPayload (language jobs)
✅ Oui


errors.py
Gestion des erreurs génériques et structurées
AppError, ValidationError, RetryableError, AlertException (avec merge_alerts for déduplication)
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
from utils_core.utils import compute_checksum, retry_on_exception  # Checksum pour embeddings, retry pour LLM/tasks
from utils_core.validators import normalize_locale, validate_lang  # Pour normalisation/validation BCP-47
from utils_core.text_cleaning import normalize_text  # Pour queries (matching), source_text (language), prompts (LLM_ai)
from utils_core.metrics import log_metric, record_metric_wrapper  # Pour monitoring latency/success
from utils_core.types import MatchFilters, TranslationJobPayload  # Typage pour matching filters, language jobs
from utils_core.env import get_env_variable  # Pour settings partagés (ex. : EMBEDDING_DIM, LLM_TIMEOUT)
from utils_core.alerts import validate_alerts, merge_alerts  # Pour SEO (language), validations (curation)
from utils_core.errors import AlertException  # Pour erreurs avec alertes dédupliquées

Exemples par App
Language
from utils_core.utils import compute_checksum
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

# Instrumenter une tâche de traduction
@record_metric_wrapper('lang.batch_translate', static_tags={'operation': 'batch'})
def batch_translate_scope(scope, source_lang, target_langs): ...

# Récupérer config partagée
batch_size = get_env_variable("LANG_BATCH_SIZE", cast="int", default=200)

Matching
from utils_core.utils import retry_on_exception
from utils_core.validators import validate_tenant_id, normalize_locale
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper, METRIC_MATCH_DIRTY_RATIO
from utils_core.types import MatchFilters

# Valider tenant_id et normaliser query
validate_tenant_id("tenant_123")
query = normalize_text("Soudure Inox 316L aéronautique", remove_accents_flag=True)

# Instrumenter une recherche hybride
@record_metric_wrapper('match.hybrid_search', static_tags={'scope': 'company'},
                       dynamic_tags=lambda: {'tenant_id': get_current_tenant()})
def hybrid_search(query, tenant_id, scope): ...

# Monitorer le dirty ratio
log_metric(METRIC_MATCH_DIRTY_RATIO, 0.05, tags={'tenant_id': 'tenant_123', 'scope': 'company'})

# Typage des filtres
filters: MatchFilters = {"sector": "aeronautique", "region": "nord"}

Curation
from utils_core.validators import validate_scope
from utils_core.alerts import validate_alerts, merge_alerts
from utils_core.errors import AlertException

# Valider un scope
validate_scope("seo:title")

# Valider et fusionner des alertes de validation
alerts = validate_alerts([{"type": "validation", "field": "concept", "message": "Invalid"}])
merged = merge_alerts([alerts], dedupe_on="type_field_message", prefer="last")

# Lever une erreur avec alertes
raise AlertException("Validation failed", alerts=[{"type": "validation", "field": "concept", "message": "Invalid"}])

LLM_ai
from utils_core.utils import retry_on_exception
from utils_core.text_cleaning import normalize_text
from utils_core.env import get_env_variable

# Normaliser un prompt
prompt = normalize_text("Summarize this text", remove_accents_flag=True)

# Réessayer un appel LLM
@retry_on_exception(exception_types=(LLMError, TimeoutError), max_attempts=3)
def enrich_text(text): ...

# Récupérer timeout LLM
timeout = get_env_variable("LLM_TIMEOUT", cast="float", default=5.0)


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

language : Translation.source_checksum, normalize_locale
matching : normalize_text pour queries, record_metric_wrapper
curation : validate_alerts, AlertException
LLM_ai : retry_on_exception, get_env_variable


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

