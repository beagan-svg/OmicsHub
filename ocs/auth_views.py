import json

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, View

from .models import UserPreferences

class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with additional fields."""
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes and attributes for modern styling
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label,
            })
            
        # Add specific attributes for each field
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'placeholder': 'Choose a username'
        })
        self.fields['email'].widget.attrs.update({
            'autocomplete': 'email',
            'placeholder': 'Enter your email address'
        })
        self.fields['first_name'].widget.attrs.update({
            'autocomplete': 'given-name',
            'placeholder': 'Your first name'
        })
        self.fields['last_name'].widget.attrs.update({
            'autocomplete': 'family-name',
            'placeholder': 'Your last name'
        })
        self.fields['password1'].widget.attrs.update({
            'autocomplete': 'new-password',
            'placeholder': 'Create a secure password'
        })
        self.fields['password2'].widget.attrs.update({
            'autocomplete': 'new-password',
            'placeholder': 'Confirm your password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

class RegisterView(CreateView):
    """User registration view."""
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            f"Account created successfully for {self.object.get_full_name() or self.object.username}! Please log in."
        )
        return response

class CustomLoginView(TemplateView):
    """Custom login view with enhanced features."""
    template_name = 'registration/login.html'
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                
                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser session
                else:
                    request.session.set_expiry(1209600)  # 2 weeks

                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please provide both username and password.")
        
        return render(request, self.template_name)

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')

class UserProfileView(LoginRequiredMixin, TemplateView):
    """User profile management view."""
    template_name = 'registration/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preferences, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        context['user_preferences'] = preferences
        return context

class UserPreferencesAPIView(LoginRequiredMixin, View):
    """Read and update the logged-in user's saved view (columns + filters)."""

    def get(self, request):
        prefs = UserPreferences.objects.filter(user=request.user).first()
        return JsonResponse({
            'column_settings': prefs.column_settings if prefs else {},
            'filter_preferences': prefs.filter_preferences if prefs else {},
        })

    def post(self, request):
        data = json.loads(request.body)
        prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
        # Update only the keys the client sent.
        if 'column_settings' in data:
            prefs.column_settings = data['column_settings']
        if 'filter_preferences' in data:
            prefs.filter_preferences = data['filter_preferences']
        prefs.save()
        return JsonResponse({'status': 'success'})

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with enhanced styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes and attributes for modern styling
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label,
            })
            
        # Add specific attributes for each field
        self.fields['old_password'].widget.attrs.update({
            'autocomplete': 'current-password',
            'placeholder': 'Enter your current password'
        })
        self.fields['new_password1'].widget.attrs.update({
            'autocomplete': 'new-password',
            'placeholder': 'Enter your new password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'autocomplete': 'new-password',
            'placeholder': 'Confirm your new password'
        })

class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change view with enhanced features."""
    template_name = 'registration/password_change_form.html'
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy('password_change_done')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your password has been changed successfully.")
        return response
