from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from lemon import models


class UserRegisterForm(UserCreationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = 'Name'

    class Meta:
        model = User
        fields = ['username', 'first_name', 'password1', 'password2']