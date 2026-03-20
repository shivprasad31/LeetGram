from django import forms

from users.models import User


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "avatar",
            "username",
            "email",
            "bio",
            "github",
            "linkedin",
            "linkedin",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "bio": forms.Textarea(attrs={"placeholder": "What kind of problems are you working on?", "rows": 5}),
            "github": forms.URLInput(attrs={"placeholder": "GitHub profile URL"}),
            "linkedin": forms.URLInput(attrs={"placeholder": "LinkedIn profile URL"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.FileInput):
                widget.attrs["class"] = "form-control rounded-4 app-input"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "form-control rounded-4 app-input app-textarea"
            else:
                widget.attrs["class"] = "form-control form-control-lg rounded-4 app-input"
