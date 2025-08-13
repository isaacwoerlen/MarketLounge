# apps/glossary/urls.py
from django.urls import path
from . import views

app_name = "glossary"

urlpatterns = [
    path('export-glossary-json/', views.export_glossary_json, name='export_glossary_json'),
    path('glossary/<str:glossary_id>/', views.glossary_detail, name='glossary_detail'),
    path('glossary/<str:glossary_id>/generate/', views.generate_glossary_node, name='generate_glossary_node'),
    path('health/', views.health, name='glossary_health'),
]