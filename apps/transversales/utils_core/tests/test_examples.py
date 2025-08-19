import pytest
from utils_core.utils import compute_checksum
from utils_core.validators import normalize_locale
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper
from utils_core.alerts import merge_alerts
from utils_core.env import get_env_variable

def test_language_examples():
    assert compute_checksum("Soudure inox 316L") == "3f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b8f3b7c3b8b7f3c7b"
    assert normalize_locale("pt_BR") == "pt-br"
    assert normalize_text("<p>Café français</p>", remove_accents_flag=True) == "cafe francais"

def test_matching_examples():
    assert normalize_text("Soudure Inox 316L aéronautique", remove_accents_flag=True) == "soudure inox 316l aeronautique"

def test_curation_examples():
    alerts = [[{"type": "validation", "field": "concept", "message": "Invalid"}]]
    merged = merge_alerts(alerts, dedupe_on="type_field_message", prefer="last")
    assert len(merged) == 1

def test_llm_ai_examples():
    assert normalize_text("Summarize this text", remove_accents_flag=True) == "summarize this text"