from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from profiles.integrations import INTEGRATION_PLATFORMS, IntegrationFieldsMixin, integration_field_widgets

from .models import User


class StyledFieldsMixin:
    default_text_class = "form-control form-control-lg rounded-4 app-input"

    def apply_bootstrap(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
                continue

            classes = self.default_text_class
            if isinstance(widget, forms.Textarea):
                classes = "form-control rounded-4 app-input app-textarea"
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, forms.FileInput):
                classes = "form-control rounded-4 app-input"
            widget.attrs["class"] = classes
            widget.attrs.setdefault("placeholder", field.label)


class SignInForm(StyledFieldsMixin, AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Enter your password"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.apply_bootstrap()

    def clean_username(self):
        return self.cleaned_data.get("username", "").lower()


class SignUpForm(IntegrationFieldsMixin, StyledFieldsMixin, UserCreationForm):
    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "bio",
            "codeforces_username",
            "leetcode_username",
            "gfg_username",
            "hackerrank_username",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Choose a username"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "bio": forms.Textarea(attrs={"placeholder": "Tell other coders what you are focused on."}),
            **integration_field_widgets(forms.TextInput),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"placeholder": "Create a password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm your password"})
        for field_name, meta in INTEGRATION_PLATFORMS.items():
            self.fields[field_name].required = False
            self.fields[field_name].label = meta["label"]
            self.fields[field_name].help_text = meta["help_text"]
        self.apply_bootstrap()

    def clean_email(self):
        return self.cleaned_data.get("email", "").lower()
