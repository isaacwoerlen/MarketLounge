# MarketLounge/config/celery.py
import os
from celery import Celery
from celery.schedules import crontab

# 1) Module Django settings : ENV d'abord, fallback ensuite
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "config.settings")
)

# 2) App Celery
app = Celery("marketlounge")

# 3) Charge la conf Django (toutes les clés CELERY_* dans settings.py)
app.config_from_object("django.conf:settings", namespace="CELERY")

# 4) Autodiscover des tasks dans INSTALLED_APPS
app.autodiscover_tasks()

# 5) Options runtime conseillées (peuvent aussi vivre dans settings.py en CELERY_*)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # jobs IA/FAISS = lourds → pas de sur-préfetch
    task_soft_time_limit=540,       # avertit à 9 min
    task_time_limit=600,            # kill à 10 min
    broker_connection_retry_on_startup=True,
)
