# apps/seo/admin.py
from django.contrib import admin
from .models import SEOBlock
from apps.language.utils import translate_fields

class SEOBlockAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'language', 'title', 'is_active', 'last_updated')
    list_filter = ('language', 'is_active', 'content_type')
    search_fields = ('title', 'description', 'og_title', 'og_description')
    actions = ['translate_seo']

    def translate_seo(self, request, queryset):
        for seo_block in queryset:
            fields = {
                'title': seo_block.title,
                'description': seo_block.description,
                'og_title': seo_block.og_title,
                'og_description': seo_block.og_description,
            }
            translate_fields(seo_block, fields, seo_block.language.code)
        self.message_user(request, "Traductions lancées pour les blocs sélectionnés.")

class SEOBlockInline(admin.TabularInline):
    model = SEOBlock
    extra = 0

admin.site.register(SEOBlock, SEOBlockAdmin)