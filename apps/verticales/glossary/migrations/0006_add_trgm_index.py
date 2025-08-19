# apps/glossary/migrations/0006_add_trgm_index.py
from django.db import migrations
from django.contrib.postgres.indexes import GinIndex

class Migration(migrations.Migration):
    dependencies = [
        ('glossary', '0005_enable_pg_trgm'),
    ]
    operations = [
        migrations.AddIndex(
            model_name='GlossaryNode',
            index=GinIndex(
                fields=['search_text'],
                name='gloss_search_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]