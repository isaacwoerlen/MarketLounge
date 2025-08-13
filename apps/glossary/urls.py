from django.urls import path
from . import views

urlpatterns = [
    path('export-glossary-json/', views.export_glossary_json, name='export_glossary_json'),
]
