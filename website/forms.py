from django import forms
from django.core.validators import RegexValidator
from django.utils.text import slugify
import re

# SA phone: +27 73 226 1199  |  27 732261199  |  073 226 1199
SA_PHONE_RE = re.compile(r'^(\+27|27|0)\s?\d{2}\s?\d{3}\s?\d{4}$')

NAME_VALIDATOR = RegexValidator(r'^[A-Za-zÀ-ÖØ-öø-ÿ \'-]+$',
                                'Only letters, spaces, apostrophes, and hyphens allowed')

class CallbackRequestForm(forms.Form):
    full_name = forms.CharField(
        max_length=120, 
        label="Full Name",
        validators=[NAME_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'autocomplete': 'name',
            'required': True
        })
    )
    phone = forms.CharField(
        max_length=30, 
        label="Phone",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+27 73 226 1199',
            'type': 'tel',
            'inputmode': 'tel',
            'autocomplete': 'tel',
            'pattern': r'^(\+27|27|0)\s?\d{2}\s?\d{3}\s?\d{4}$',
            'required': True
        })
    )
    best_time = forms.ChoiceField(
        choices=[
            ("", "Select a time"),
            ("asap", "Call me ASAP"),
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("evening", "Evening"),
        ],
        required=False,
        label="Best time to call (optional)",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'autocomplete': 'off'
        })
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 3,
            'class': 'form-control',
            'placeholder': 'Anything we should know?',
            'autocomplete': 'off',
            'maxlength': '500'
        }), 
        required=False, 
        label="Notes (optional)",
        max_length=500
    )
    page = forms.CharField(widget=forms.HiddenInput(), required=False)  # where the request originated
    
    # Honeypot field for spam protection
    company = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'hp',
            'style': 'display: none;',
            'autocomplete': 'off',
            'tabindex': '-1'
        })
    )

    def clean_full_name(self):
        v = (self.cleaned_data.get("full_name") or "").strip()
        if len(v) < 2:
            raise forms.ValidationError("Please enter your full name.")
        if len(v) > 120:
            raise forms.ValidationError("Name is too long.")
        return v
    
    def clean_company(self):
        # Honeypot field - should be empty
        if self.cleaned_data.get("company"):
            raise forms.ValidationError("Invalid submission.")
        return ""

    def _normalize_phone(self, raw: str) -> str:
        # remove spaces
        v = (raw or "").replace(" ", "")
        # leading 0XXXXXXXXX -> +27XXXXXXXXX
        if re.fullmatch(r'0\d{9}', v):
            v = "+27" + v[1:]
        # 27XXXXXXXXX -> +27XXXXXXXXX
        if re.fullmatch(r'27\d{9}', v):
            v = "+" + v
        return v

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        if not raw:
            raise forms.ValidationError("Phone number is required.")
        norm = self._normalize_phone(raw)
        if not SA_PHONE_RE.match(norm):
            raise forms.ValidationError("Use SA format, e.g. +27 73 226 1199 or 073 226 1199.")
        return norm


class ContactForm(forms.Form):
    first_name = forms.CharField(
        max_length=100,
        validators=[NAME_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name',
            'autocomplete': 'given-name',
            'required': True
        })
    )
    last_name = forms.CharField(
        max_length=100,
        validators=[NAME_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name',
            'autocomplete': 'family-name',
            'required': True
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@company.com',
            'autocomplete': 'email',
            'required': True
        })
    )
    company = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company name (optional)',
            'autocomplete': 'organization'
        })
    )

    # We'll validate subject against a known set (passed in from the view),
    # but still accept any non-empty string and slugify it.
    subject = forms.CharField(
        max_length=120, 
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )

    message = forms.CharField(
        min_length=10,
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Tell us about your project requirements, timeline, and any specific features you need...',
            'required': True,
            'maxlength': '2000'
        })
    )
    honeypot = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'style': 'display: none;',
            'autocomplete': 'off',
            'tabindex': '-1'
        })
    )

    # Optional: pass allowed subjects from the view so UI and backend stay in sync
    def __init__(self, *args, **kwargs):
        # kwargs.pop allows missing key without KeyError
        self.allowed_subjects = kwargs.pop("allowed_subjects", {})
        super().__init__(*args, **kwargs)
        
        # Populate subject choices if provided
        if self.allowed_subjects:
            choices = [("", "Select a service...")]
            choices.extend([(slug, label) for slug, label in self.allowed_subjects.items()])
            self.fields['subject'].widget.choices = choices

    def clean_honeypot(self):
        if self.cleaned_data.get("honeypot"):
            raise forms.ValidationError("Invalid submission.")
        return ""

    def clean_first_name(self):
        v = (self.cleaned_data.get("first_name") or "").strip()
        if len(v) < 2:
            raise forms.ValidationError("Please enter your first name.")
        if len(v) > 100:
            raise forms.ValidationError("First name is too long.")
        return v

    def clean_last_name(self):
        v = (self.cleaned_data.get("last_name") or "").strip()
        if len(v) < 2:
            raise forms.ValidationError("Please enter your last name.")
        if len(v) > 100:
            raise forms.ValidationError("Last name is too long.")
        return v

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required.")
        
        # Basic email validation beyond Django's default
        if len(email) > 254:
            raise forms.ValidationError("Email address is too long.")
        
        # Check for common typos
        common_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        if '@' in email:
            domain = email.split('@')[1]
            # You could add domain validation here if needed
        
        return email
    
    def clean_message(self):
        message = (self.cleaned_data.get("message") or "").strip()
        if len(message) < 10:
            raise forms.ValidationError("Please provide more details about your project (at least 10 characters).")
        if len(message) > 2000:
            raise forms.ValidationError("Message is too long. Please keep it under 2000 characters.")
        return message

    def clean_subject(self):
        raw = (self.cleaned_data.get("subject") or "").strip()
        if not raw:
            raise forms.ValidationError("Please select a subject.")
        slug = slugify(raw)

        # If we were given allowed subjects, ensure it matches either a slug or label.
        if self.allowed_subjects:
            allowed_slugs = set(self.allowed_subjects.keys())
            allowed_labels = {slugify(lbl): lbl for lbl in self.allowed_subjects.values()}
            if slug not in allowed_slugs and slug not in allowed_labels:
                raise forms.ValidationError("Please choose a valid subject.")
        return slug

    # Helper to get a nice label for the subject (useful in emails)
    def subject_label(self):
        slug = self.cleaned_data.get("subject") or ""
        if self.allowed_subjects:
            # If slug is a key, use label; else try reverse-lookup via slugified labels.
            if slug in self.allowed_subjects:
                return self.allowed_subjects[slug]
            for lbl in self.allowed_subjects.values():
                if slugify(lbl) == slug:
                    return lbl
        # fallback to the slug if nothing else
        return slug.replace("-", " ").title()