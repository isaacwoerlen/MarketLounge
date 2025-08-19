"""
Django settings for MarketLounge (DEV).
Organized by thematic sections for clarity.
"""
from pathlib import Path
import os
import re
from decouple import config, Csv
import dj_database_url

# ----- Chemins de base -----
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----- Sécurité -----
SECRET_KEY = config("SECRET_KEY", default="dev-only-secret-key")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----- Langues et internationalisation -----
ACTIVE_LANGS_FALLBACK = config("ACTIVE_LANGS", default="fr,en", cast=Csv())
for lang in ACTIVE_LANGS_FALLBACK:
    if not re.match(r'^[a-z]{2}(-[a-z]{2})?$', lang):
        raise ValueError(f"Invalid language code in ACTIVE_LANGS: {lang}")
DEFAULT_LANG_FALLBACK = config("DEFAULT_LANG", default="fr")
LANG_CACHE_TTL = config("LANG_CACHE_TTL", default=300, cast=int)
LANG_ENABLE_API = config("LANG_ENABLE_API", default=False, cast=bool)
LANGUAGE_CODE = DEFAULT_LANG_FALLBACK
LANGUAGES = [(code, code.upper()) for code in ACTIVE_LANGS_FALLBACK]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# ----- Base de données -----
DATABASES = {
    "default": dj_database_url.config(
        default=config(
            "DATABASE_URL",
            default="postgres://postgres:postgres@db:5432/postgres"
        ),
        conn_max_age=600,
    )
}

# ----- Cache -----
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("CACHE_URL", default="redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# ----- Celery -----
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_RATE_LIMIT = {
    'transversales.language.tasks.run_batch_translation_items': '100/m',
    'transversales.language.tasks.run_vectorize_scopes': '50/m'
}

# ----- API et authentification -----
AUTH_USER_MODEL = "auth.User"
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
LANGUAGE_STAFF_GLOBAL = config("LANGUAGE_STAFF_GLOBAL", default=True, cast=bool)

# ----- Mistral et vectorisation -----
MISTRAL_API_KEY = config("MISTRAL_API_KEY", default="")
MISTRAL_TRANSLATE_MODEL = config("MISTRAL_TRANSLATE_MODEL", default="mistral-large-latest")
MISTRAL_API_BASE = config("MISTRAL_API_BASE", default="https://api.mistral.ai/v1")
MISTRAL_ENRICH_MODEL = config("MISTRAL_ENRICH_MODEL", default="mistral-large-latest")
LLM_TIMEOUT = config("LLM_TIMEOUT", default=5, cast=int)
LLM_FALLBACK_PROVIDER = config("LLM_FALLBACK_PROVIDER", default="openai")
FAISS_ENABLED = config("FAISS_ENABLED", default=True, cast=bool)
PGVECTOR_ENABLED = config("PGVECTOR_ENABLED", default=True, cast=bool)
EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = config("EMBEDDING_DIM", default=384, cast=int)
FAISS_INDEX_DIR = BASE_DIR / config("FAISS_INDEX_DIR", default="faiss_index")
LANG_EMBED_SYNC = config("LANG_EMBED_SYNC", default=False, cast=bool)

# ----- Logging -----
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "class": "logging.FileHandler",
            "filename": str(LOGS_DIR / "django.log"),
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO"},
        "transversales.language": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        "transversales.faiss_pgvector": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        "transversales.LLM_ai": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
    },
}

# ----- Métriques -----
METRICS_BACKEND = config("METRICS_BACKEND", default="prometheus")

# ----- Applications -----
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "pgvector.django",
    "corsheaders",
    "transversales.language.apps.LanguageConfig",
    "transversales.LLM_ai",
    "transversales.seo",
    "transversales.media",
    "transversales.metrics",
    "transversales.permissions",
    "transversales.taxonomy",
    "transversales.utils_core",
    "transversales.matching",
    "verticales.glossary",
    "verticales.dico",
    "verticales.companies",
    "verticales.activation",
    "verticales.logs",
    "verticales.market",
    "verticales.api",
    "rest_framework",
    "django_celery_beat",
]

# ----- Middleware -----
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ----- URLs et WSGI -----
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ----- Templates -----
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ----- Clés diverses -----
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TEXT_SEARCH_BACKEND = config("TEXT_SEARCH_BACKEND", default="trigram")  # 'tsvector' en V02

# ----- Validation -----
assert EMBEDDING_DIM > 0, "EMBEDDING_DIM must be positive"
assert FAISS_ENABLED or PGVECTOR_ENABLED, "At least one of FAISS_ENABLED or PGVECTOR_ENABLED must be True"
assert EMBEDDING_MODEL.startswith("sentence-transformers/"), "Invalid EMBEDDING_MODEL"