"""Root URL configuration for the OCS project.

Application URLs live in ocs/urls.py under the 'ocs:' namespace.
Authentication URLs are project-level and intentionally un-namespaced, because
Django's auth views (e.g. password reset) and templates reverse them by plain
name ('login', 'password_reset_confirm', ...).
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from ocs.auth_views import (
    CustomLoginView,
    RegisterView,
    logout_view,
    UserProfileView,
    UserPreferencesAPIView,
    CustomPasswordChangeView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication (project-level, un-namespaced)
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', logout_view, name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('password_change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html'
    ), name='password_change_done'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('api/preferences/', UserPreferencesAPIView.as_view(), name='user_preferences_api'),

    # Application
    path('', include('ocs.urls')),
]

# Google SSO routes (e.g. /accounts/google/login/) — only when enabled.
if settings.ENABLE_GOOGLE_SSO:
    urlpatterns += [path('accounts/', include('allauth.urls'))]
