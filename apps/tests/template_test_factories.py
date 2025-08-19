# apps/<app_name>/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from <app_name>.models import <ModelName1>, <ModelName2>  # Importer tous les modèles

# Factory générique pour chaque modèle
class <ModelName1>Factory(DjangoModelFactory):
    class Meta:
        model = <ModelName1>

    # Champs simples
    <field1> = factory.Faker('word')  # e.g., name
    <field2> = factory.Sequence(lambda n: f'code-{n}')  # e.g., code
    is_active = True

    # Champs JSON (si applicable)
    <json_field> = factory.List([
        factory.Dict({'type': factory.Faker('word'), 'message': factory.Faker('sentence')})
    ])  # e.g., alerts

    # Champs relationnels (si applicable)
    <foreign_key> = factory.SubFactory('<OtherModel>Factory')  # e.g., language=LanguageFactory

    # Champs IA (si applicable)
    embedding = factory.LazyFunction(lambda: b'mocked_vector')  # Simuler embedding

# Exemple pour language
class LanguageFactory(DjangoModelFactory):
    class Meta:
        model = Language

    code = factory.Sequence(lambda n: f'lang-{n}')
    name = factory.Faker('word')
    is_active = True
    is_default = False
    priority = 5

class TranslatableKeyFactory(DjangoModelFactory):
    class Meta:
        model = TranslatableKey

    scope = factory.Faker('word')
    key = factory.Sequence(lambda n: f'key-{n}')
    checksum = factory.Faker('sha256')
    is_blocking = False
    prompt_template = factory.Dict({'tone': 'formal', 'max_length': 100})
    tenant_id = factory.Faker('uuid4')

class TranslationFactory(DjangoModelFactory):
    class Meta:
        model = Translation

    key = factory.SubFactory(TranslatableKeyFactory)
    language = factory.SubFactory(LanguageFactory)
    text = factory.Faker('sentence')
    version = 1
    alerts = factory.List([factory.Dict({'type': 'warning', 'message': factory.Faker('sentence')})])
    reviewer = factory.Faker('name')
    embedding = factory.LazyFunction(lambda: b'mocked_vector')

class TranslationJobFactory(DjangoModelFactory):
    class Meta:
        model = TranslationJob

    name = factory.Faker('word')
    state = 'queued'
    source_locale = 'en'
    target_locales = factory.List(['fr', 'de'])
    scope_filter = factory.List(['homepage', 'product'])
    stats = factory.Dict({'total': 100, 'translated': 80})
    errors = factory.List([])