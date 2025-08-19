# apps/transversales/LLM_ai/services.py
import re
import time
from typing import Dict, List, Optional, Tuple
from django.core.exceptions import ValidationError

# Placeholder protection
PLACEHOLDER_PATTERNS = [r"\{\{.*?\}\}", r"\{[a-zA-Z0-9_]+\}", r"%\w", r"\$\w+"]
PH_RE = re.compile("|".join(PLACEHOLDER_PATTERNS))

def protect_placeholders(txt: str) -> tuple[str, Dict[str, str]]:
    mapping, out = {}, txt or ""
    for i, m in enumerate(PH_RE.findall(out)):
        token = f"§PH_{i}§"
        mapping[token] = m
        out = out.replace(m, token, 1)
    return out, mapping

def restore_placeholders(txt: str, mapping: Dict[str, str]) -> str:
    for k, v in mapping.items():
        txt = txt.replace(k, v)
    return txt

# Translator abstraction
class Translator:
    def translate(self, text: str, src: str, tgt: str, prompt: Optional[Dict]) -> str:
        raise NotImplementedError

class MistralTranslator(Translator):
    def translate(self, text: str, src: str, tgt: str, prompt: Optional[Dict]) -> str:
        from mistralai import mistral_translate  # Assume external dependency
        return mistral_translate(text=text, source_lang=src, target_lang=tgt, prompt_template=prompt)

PROVIDERS = [MistralTranslator()]

def with_retry(fn, *, retries: int = 2, base_sleep: float = 0.8):
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if i == retries:
                raise ValidationError(f"Translation failed: {str(e)}") from e
            time.sleep(base_sleep * (2 ** i))

def apply_glossary(text: str, src_lang: str, tgt_lang: str) -> Dict:
    """Crochet pour glossaire (no-op pour MVP)."""
    return {}

def translate_text(source_text: str, source_lang: str, target_lang: str, prompt_template: Optional[Dict] = None) -> Tuple[str, Dict]:
    """Centralise les appels IA pour traduction, renvoie (texte, meta)."""
    src_protected, ph_map = protect_placeholders(source_text)
    rules = apply_glossary(src_protected, source_lang, target_lang)
    if prompt_template and rules:
        prompt_template = {**prompt_template, "glossary": rules}

    last_err = None
    for provider in PROVIDERS:
        try:
            translated = with_retry(lambda: provider.translate(src_protected, source_lang, target_lang, prompt_template))
            meta = {"provider": "mistral", "model": "large-latest"}  # Adaptez selon le provider réel
            return restore_placeholders(translated, ph_map), meta
        except Exception as e:
            last_err = e
            continue
    raise ValidationError(f"All translators failed ({source_lang}->{target_lang}): {last_err}")