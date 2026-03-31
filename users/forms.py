from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from integrations.services import CodeforcesService, LeetCodeService, PlatformServiceError
from profiles.integrations import validate_integration_username

from .models import User
from .services import normalize_email


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


class OTPRegistrationForm(StyledFieldsMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Create a password"}),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Confirm your password"}),
    )

    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Choose a username"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields["username"].widget.attrs.update({"autocomplete": "username"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})

    def clean_email(self):
        email = normalize_email(self.cleaned_data.get("email", ""))
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        if password1:
            provisional_user = User(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                password_validation.validate_password(password1, provisional_user)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data


class ProfileSetupForm(StyledFieldsMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["bio", "leetcode_username", "codeforces_username"]
        widgets = {
            "bio": forms.Textarea(attrs={"placeholder": "Tell others what you are practicing right now.", "rows": 5}),
            "leetcode_username": forms.TextInput(attrs={"placeholder": "Enter your LeetCode username", "autocomplete": "off"}),
            "codeforces_username": forms.TextInput(attrs={"placeholder": "Enter your Codeforces handle", "autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bio"].required = False
        self.fields["leetcode_username"].required = False
        self.fields["codeforces_username"].required = False
        self.apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        seen_values = {}

        for field_name, label in (
            ("leetcode_username", "LeetCode"),
            ("codeforces_username", "Codeforces"),
        ):
            value = (cleaned_data.get(field_name) or "").strip()
            try:
                normalized = validate_integration_username(value, label)
            except forms.ValidationError as exc:
                self.add_error(field_name, exc)
                continue
            cleaned_data[field_name] = normalized
            if not normalized:
                continue

            duplicate_key = normalized.casefold()
            if duplicate_key in seen_values:
                self.add_error(field_name, f"This username is already used for {seen_values[duplicate_key]}.")
                continue
            seen_values[duplicate_key] = label

        validators = {
            "leetcode_username": ("LeetCode", LeetCodeService),
            "codeforces_username": ("Codeforces", CodeforcesService),
        }
        for field_name, (label, service_class) in validators.items():
            username = cleaned_data.get(field_name)
            if not username:
                continue
            try:
                if not service_class().validate_username(username):
                    self.add_error(field_name, f"{label} profile not found for '{username}'.")
            except PlatformServiceError as exc:
                self.add_error(field_name, f"Could not verify {label} username right now: {exc}")

        return cleaned_data
