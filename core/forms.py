from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserAddress

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove all help text and make it super simple
        self.fields['password1'].help_text = 'Any password is allowed - use whatever you want!'
        self.fields['password2'].help_text = 'Just repeat your password.'
        self.fields['username'].help_text = 'Choose any username you like.'

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

class UserProfileForm(forms.ModelForm):
    """Form for editing user profile details"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
            
        # Add placeholders
        self.fields['username'].widget.attrs.update({'placeholder': 'Enter username'})
        self.fields['email'].widget.attrs.update({'placeholder': 'Enter email address'})
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Enter first name'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Enter last name'})

class UserAddressForm(forms.ModelForm):
    """Form for adding and editing user addresses"""
    class Meta:
        model = UserAddress
        fields = '__all__'
        exclude = ['user'] # Exclude user since it will be set automatically

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes and placeholders
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            if field_name == 'first_name':
                field.widget.attrs.update({'placeholder': 'Enter first name'})
            elif field_name == 'last_name':
                field.widget.attrs.update({'placeholder': 'Enter last name'})
            elif field_name == 'company':
                field.widget.attrs.update({'placeholder': 'Enter company name (optional)'})
            elif field_name == 'address':
                field.widget.attrs.update({'placeholder': 'Street address, P.O. Box, etc.'})
            elif field_name == 'apartment':
                field.widget.attrs.update({'placeholder': 'Apt, Suite, Unit, etc. (optional)'})
            elif field_name == 'city':
                field.widget.attrs.update({'placeholder': 'Enter city'})
            elif field_name == 'state':
                field.widget.attrs.update({'placeholder': 'Enter state/province'})
            elif field_name == 'postal_code':
                field.widget.attrs.update({'placeholder': 'Enter postal code'})
            elif field_name == 'phone':
                field.widget.attrs.update({'placeholder': 'Enter phone number'})
