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
