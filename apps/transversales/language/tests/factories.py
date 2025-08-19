# apps/transversales/language/tests/factories.py
import factory
import uuid
from factory.django import DjangoModelFactory
from transversales.language.models import Language, TranslatableKey, Translation, TranslationJob
import numpy as np

class LanguageFactory(DjangoModelFactory):
    class Meta:
        model = Language

    code = factory.Iterator(["fr", "en", "pt-br", "es"])
    name = factory.Faker('word')
    is_active = True
    is_default = factory.LazyAttribute(lambda o: o.code == "fr")
    priority = factory.Sequence(lambda n: n + 1)

class TranslatableKeyFactory(DjangoModelFactory):
    class Meta:
        model = TranslatableKey

    scope = factory.Faker('word')
    key = factory.Sequence(lambda n: f'key-{n}')
    checksum = factory.Faker('sha256')
    is_blocking = False
    prompt_template = factory.Dict({'tone': 'formal', 'max_length': 100})
    tenant_id = factory.LazyFunction(lambda: f"tenant_{uuid.uuid4().hex[:8]}")

class TranslationFactory(DjangoModelFactory):
    class Meta:
        model = Translation

    key = factory.SubFactory(TranslatableKeyFactory)
    language = factory.SubFactory(LanguageFactory)
    text = factory.Faker('sentence')
    version = 1
    alerts = factory.List([
        factory.Dict({
            'type': factory.Faker('word'),
            'field': 'text',
            'message': factory.Faker('sentence')
        })
    ])
    embedding = factory.LazyFunction(lambda: list(np.random.rand(384)))
    source_checksum = factory.Faker('sha256')
    origin = "human"
    tenant_id = factory.LazyAttribute(lambda o: o.key.tenant_id)

class TranslationJobFactory(DjangoModelFactory):
    class Meta:
        model = TranslationJob

    name = factory.Faker('word')
    state = factory.Iterator(['queued', 'running', 'done', 'failed'])
    source_locale = 'fr'
    target_locales = factory.List(['en', 'pt-br'])
    scope_filter = factory.List(['glossary', 'seo'])
    stats = factory.Dict({'processed': 100, 'per_lang': {'en': 50, 'pt-br': 50}, 'errors': 0})
    errors = factory.List([])
    tenant_id = factory.LazyFunction(lambda: f"tenant_{uuid.uuid4().hex[:8]}")
    