# apps/glossary/urls.py
from django.urls import path
from . import views

app_name = "glossary"

urlpatterns = [
    path("glossary/<str:glossary_id>/", views.glossary_detail, name="glossary_detail"),
    path("glossary/<str:glossary_id>/generate/", views.generate_glossary_node, name="generate_glossary_node"),
    path("glossary/health/", views.health, name="glossary_health"),
]
