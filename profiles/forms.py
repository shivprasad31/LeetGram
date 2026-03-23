from django import forms

from integrations.models import IntegrationStatus
from integrations.services import CodeforcesService, GFGService, HackerRankService, LeetCodeService, PlatformServiceError
from users.models import User

from .integrations import INTEGRATION_PLATFORMS, IntegrationFieldsMixin, integration_field_widgets


PLATFORM_VALIDATORS = {
    "codeforces_username": CodeforcesService,
    "leetcode_username": LeetCodeService,
    "gfg_username": GFGService,
    "hackerrank_username": HackerRankService,
}


class ProfileUpdateForm(IntegrationFieldsMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "avatar",
            "username",
            "email",
            "bio",
            "github",
            "linkedin",
            "codeforces_username",
            "leetcode_username",
            "gfg_username",
            "hackerrank_username",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "bio": forms.Textarea(attrs={"placeholder": "What kind of problems are you working on?", "rows": 5}),
            "github": forms.URLInput(attrs={"placeholder": "GitHub profile URL"}),
            "linkedin": forms.URLInput(attrs={"placeholder": "LinkedIn profile URL"}),
            **integration_field_widgets(forms.TextInput),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, meta in INTEGRATION_PLATFORMS.items():
            self.fields[field_name].required = False
            self.fields[field_name].label = meta["label"]
            self.fields[field_name].help_text = meta["help_text"]

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.FileInput):
                widget.attrs["class"] = "form-control rounded-4 app-input"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "form-control rounded-4 app-input app-textarea"
            else:
                widget.attrs["class"] = "form-control form-control-lg rounded-4 app-input"

    def clean_email(self):
        return self.cleaned_data.get("email", "").lower()


class ProfileIntegrationForm(IntegrationFieldsMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = list(INTEGRATION_PLATFORMS.keys())
        widgets = integration_field_widgets(forms.TextInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, meta in INTEGRATION_PLATFORMS.items():
            self.fields[field_name].required = False
            self.fields[field_name].label = meta["label"]
            self.fields[field_name].help_text = meta["help_text"]
            self.fields[field_name].widget.attrs["class"] = "form-control form-control-lg rounded-4 app-input"

    def clean(self):
        cleaned_data = super().clean()
        for field_name, service_class in PLATFORM_VALIDATORS.items():
            username = cleaned_data.get(field_name)
            if not username:
                continue
            label = INTEGRATION_PLATFORMS[field_name]["label"]
            try:
                if not service_class().validate_username(username):
                    self.add_error(field_name, f"{label} profile not found for '{username}'.")
            except PlatformServiceError as exc:
                self.add_error(field_name, f"Could not verify {label} username right now: {exc}")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            IntegrationStatus.objects.filter(user=user, platform__in=[
                field_name.replace("_username", "") for field_name in self.changed_data
            ]).update(status="success", error_message="")
        return user