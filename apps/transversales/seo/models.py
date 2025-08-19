# apps/seo/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.transversales.language.utils import get_active_langs
from apps.transversales.language.utils import translate_fields

# Ce modèle stocke les métadonnées SEO/OG et est lié à n’importe quel objet via GenericForeignKey.
class SEOBlock(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=100)  # Supporte UUID ou autres
    content_object = GenericForeignKey("content_type", "object_id")

    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, help_text="Titre SEO (60-70 chars)")
    description = models.TextField(blank=True, help_text="Description meta (150-160 chars)")
    keywords = models.JSONField(default=list, blank=True, help_text="Liste de mots-clés")
    og_title = models.CharField(max_length=255, blank=True, help_text="Titre OG (60-90 chars)")
    og_description = models.TextField(blank=True, help_text="Description OG (100-200 chars)")
    og_image_url = models.URLField(blank=True, help_text="URL de l'image OG")
    twitter_card = models.CharField(
        max_length=50,
        blank=True,
        choices=[('summary', 'Summary'), ('summary_large_image', 'Summary Large Image')],
        help_text="Type de Twitter Card"
    )
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("content_type", "object_id", "language")
        verbose_name = "Bloc SEO"
        verbose_name_plural = "Blocs SEO"

    def __str__(self):
        return f"SEO pour {self.content_object} en {self.language.code}"

# Crée un SEOBlock vide pour chaque langue active lors de la création d’un objet (ex. GlossaryNode)
@receiver(post_save)
def create_seo_blocks(sender, instance, created, **kwargs):
    if created and not issubclass(sender, SEOBlock):
        content_type = ContentType.objects.get_for_model(sender)
        for lang in get_active_langs():
            SEOBlock.objects.get_or_create(
                content_type=content_type,
                object_id=str(instance.pk),
                language=lang,
                defaults={
                    'title': str(instance)[:255],  # Valeur par défaut
                    'description': '',
                }
            )
# Déclenche la traduction via language après la sauvegarde d’un SEOBlock saisi manuellement :
@receiver(post_save, sender=SEOBlock)
def trigger_seo_translation(sender, instance, created, **kwargs):
    if created or instance._state.adding is False:  # Nouvelle création ou mise à jour
        fields = {
            'title': instance.title,
            'description': instance.description,
            'og_title': instance.og_title,
            'og_description': instance.og_description,
        }
        translate_fields(instance, fields, instance.language.code)