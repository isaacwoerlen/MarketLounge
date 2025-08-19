# apps/glossary/migrations/0005_enable_pg_trgm.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('glossary', '0004_alter_glossarynode_created_at'),
    ]
    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS pg_trgm;"),
    ]