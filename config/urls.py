# config/urls.py
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

def home(request):
    return HttpResponse(
        "<h1>Bienvenue sur MarketLounge 👋</h1>"
        "<p>Accédez à <a href='/admin/'>l’admin</a>.</p>"
    )

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("", include(("apps.glossary.urls", "glossary"), namespace="glossary")),
]
