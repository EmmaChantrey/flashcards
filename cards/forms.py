# tell the app whether you knew the answer or not

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.forms.models import inlineformset_factory
from .models import FlashcardSet, Flashcard

class FlashcardSetTitle(forms.ModelForm):
    class Meta:
        model = FlashcardSet
        fields = ['name']

FlashcardTermDefs = inlineformset_factory(
    FlashcardSet,
    Flashcard,
    fields=['term', 'definition'],
    extra=0,
    can_delete=True
)

class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text='Required. Enter a valid email address.',
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username'}),
            'password1': forms.PasswordInput(attrs={'placeholder': 'Password'}),
            'password2': forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}),
        }


# class CardCheckForm(forms.Form):
#     card_id = forms.IntegerField(required=True)
#     solved = forms.BooleanField(required=False)

