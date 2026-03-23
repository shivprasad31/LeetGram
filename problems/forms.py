from django import forms
from .models import ProblemDifficulty, Tag

class SolvedProblemForm(forms.Form):
    title = forms.CharField(
        max_length=255, 
        widget=forms.TextInput(attrs={"class": "form-control rounded-4 app-input", "placeholder": "e.g. Two Sum"})
    )
    statement = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control rounded-4 app-input app-textarea", "placeholder": "Describe the problem logic...", "rows": 4})
    )
    url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control rounded-4 app-input", "placeholder": "https://..."})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control rounded-4 app-input app-textarea", "placeholder": "Add your solution notes here...", "rows": 4})
    )
    difficulty = forms.ModelChoiceField(
        queryset=ProblemDifficulty.objects.all(),
        widget=forms.Select(attrs={"class": "form-select rounded-4 app-input"})
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select rounded-4 app-input", "size": "5"})
    )
