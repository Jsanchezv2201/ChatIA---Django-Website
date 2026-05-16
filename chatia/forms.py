from django import forms
from django.conf import settings


class PromptForm(forms.Form):
    prompt = forms.CharField(
        label='Mensaje',
        max_length=1500,
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'placeholder': 'Escribe tu mensaje...',
            }
        ),
    )


class ConversationTitleForm(forms.Form):
    title = forms.CharField(
        label='Título',
        max_length=120,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Nuevo título de la conversación',
                'class': 'form-control form-control-sm',
                'autocomplete': 'off',
            }
        ),
    )


class UserPreferenceForm(forms.Form):
    llm_model = forms.ChoiceField(
        label='Modelo preferido',
        required=False,
        choices=settings.LLM_MODEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    llm_max_tokens = forms.IntegerField(
        label='Tokens máximos personales',
        min_value=64,
        max_value=65536,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    llm_temperature = forms.FloatField(
        label='Temperatura (0.0 - 2.0)',
        min_value=0.0,
        max_value=2.0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
    )
