# apps/glossary/tasks.py
from celery import shared_task
from django.core.management import call_command

@shared_task
def run_generate_glossary(glossary_ids):
    for gid in glossary_ids:
        try:
            call_command("generate_glossary", gid)
        except Exception:
            pass

@shared_task
def monthly_glossary_scan():
    call_command('generate_glossary', all_pending=True)