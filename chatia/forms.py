from django import forms


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
