# apps/glossary/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import GlossaryNode
from apps.language.utils import get_active_langs

# Champs multilingues "virtuels" exposés dans l'admin
MULTILINGUAL_FIELDS = {
    "label":               (forms.CharField, {"required": False}),
    "definition":          (forms.CharField, {"required": False, "widget": forms.Textarea}),
    "procede":             (forms.CharField, {"required": False, "widget": forms.Textarea}),
    "explication_technique": (forms.CharField, {"required": False, "widget": forms.Textarea}),
    "seo_keywords":        (forms.CharField, {"required": False}),
    "seo_description":     (forms.CharField, {"required": False, "widget": forms.Textarea}),
}

# Champs exigés selon le type (surtension "métier/opération/variante")
TYPE_FIELDS = {
    "metier":   ["label", "definition", "seo_keywords", "seo_description"],
    "operation":["label", "definition", "seo_keywords", "seo_description"],
    "variante": ["label", "definition", "procede", "explication_technique", "seo_keywords", "seo_description"],
}

class GlossaryNodeForm(forms.ModelForm):
    """
    Form admin pour GlossaryNode :
    - expose des champs multilingues plats (label_fr, definition_en, ...)
    - pack en JSON avant save()
    - applique des garde-fous de gouvernance
    """

    class Meta:
        model = GlossaryNode
        # On n'expose pas les champs systèmes/computés
        fields = [
            "type", "parent", "node_id",
            "is_active", "version",
            # les champs multilingues seront ajoutés dynamiquement en __init__
        ]

    class Media:
        js = ("glossary/glossary_admin.js",)
        css = {"all": ("glossary/glossary_admin.css",)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, "instance", None)
        node_type = getattr(inst, "type", None) or self.initial.get("type") or "metier"
        active_fields = TYPE_FIELDS.get(node_type, [])

        # Ajout dynamique des champs multilingues utiles
        for prefix in active_fields:
            field_class, options = MULTILINGUAL_FIELDS[prefix]
            for lang in ACTIVE_LANGS:
                fname = f"{prefix}_{lang}"
                label = f"{prefix.replace('_', ' ').capitalize()} ({lang})"
                self.fields[fname] = field_class(label=label, **options)

                # Initialiser depuis l'instance (édition)
                if inst and inst.pk:
                    if prefix.startswith("seo_"):
                        seo_lang = (inst.seo or {}).get(lang, {})
                        if prefix == "seo_keywords":
                            kws = seo_lang.get("keywords", [])
                            self.fields[fname].initial = ", ".join(kws) if isinstance(kws, list) else ""
                        else:
                            self.fields[fname].initial = seo_lang.get("description", "")
                    else:
                        self.fields[fname].initial = (getattr(inst, prefix, {}) or {}).get(lang, "")

        # Option UX : désactiver l'activation si pas encore reviewé
        if "is_active" in self.fields and not (inst and inst.reviewed_by):
            self.fields["is_active"].help_text = "Cette case restera invalide tant que le nœud n'a pas été reviewé."
        # node_id facultatif : sera généré s'il est vide (slugify(labels/...))
        self.fields["node_id"].required = False

    # ---- Helpers internes ----
    def _pack_multilang(self, cleaned, prefix):
        """
        Packe prefix_{lang} -> {lang: value, ...} en ignorant les vides.
        """
        data = {}
        for lang in ACTIVE_LANGS:
            val = cleaned.get(f"{prefix}_{lang}")
            if val:
                data[lang] = val
        return data

    def clean(self):
        cleaned = super().clean()

        # 1) Au moins un label dans ACTIVE_LANGS
        labels = self._pack_multilang(cleaned, "label")
        if not any(labels.values()):
            raise ValidationError(f"Renseigner au moins un label parmi : {', '.join(ACTIVE_LANGS)}.")
        cleaned["labels_json"] = labels

        # 2) Autres champs multilingues
        for prefix in ["definition", "procede", "explication_technique"]:
            cleaned[f"{prefix}_json"] = self._pack_multilang(cleaned, prefix)

        # 3) SEO
        seo = {}
        for lang in ACTIVE_LANGS:
            kws_raw = cleaned.get(f"seo_keywords_{lang}") or ""
            kws = [k.strip() for k in kws_raw.split(",") if len(k.strip()) > 1]
            desc = cleaned.get(f"seo_description_{lang}") or ""
            if kws or desc:
                seo[lang] = {"keywords": kws, "description": desc}
        cleaned["seo_json"] = seo

        # 4) Gouvernance : empêcher la publication sans review/version
        # On simule l'instance post-save pour bénéficier des validations modèle
        temp = GlossaryNode(
            type=cleaned.get("type", self.instance.type if self.instance else None),
            parent=cleaned.get("parent", self.instance.parent if self.instance else None),
            node_id=cleaned.get("node_id") or (self.instance.node_id if self.instance else None),
            labels=cleaned["labels_json"],
            definition=cleaned.get("definition_json", {}),
            procede=cleaned.get("procede_json", {}),
            explication_technique=cleaned.get("explication_technique_json", {}),
            seo=cleaned["seo_json"],
            is_active=cleaned.get("is_active", self.instance.is_active if self.instance else False),
            version=cleaned.get("version", self.instance.version if self.instance else 1),
            reviewed_by=getattr(self.instance, "reviewed_by", None),  # reviewé via admin/flow, pas via la form
        )
        temp.clean()  # applique les règles hiérarchie + publication
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        c = self.cleaned_data

        # Injecte les JSON packés
        obj.labels = c.get("labels_json", {})
        obj.definition = c.get("definition_json", {})
        obj.procede = c.get("procede_json", {})
        obj.explication_technique = c.get("explication_technique_json", {})
        obj.seo = c.get("seo_json", {})

        if commit:
            obj.save()
            self.save_m2m()
        return obj
