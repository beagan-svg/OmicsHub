"""
Django settings for database_ocs project.
Base settings to be imported by development.py and production.py
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_tables2',
    'django_filters',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'ocs.apps.OcsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',  # compress large JSON/HTML responses
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'ocs.middleware.SourceMapMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ocs.context_processors.template_utils',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Additional static files directories
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Django Tables2
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"

# Multi-User Authentication Settings
# Using Django's default User model for now

# Authentication URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Session Configuration for Multi-User
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours default
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Enhanced Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# OCS Command Execution Settings
# Controls whether OCS commands are actually executed or just logged
# Override in development.py or production.py as needed
EXECUTE_OCS_COMMANDS = True

# ---------------------------------------------------------------------------
# Google SSO (django-allauth) — optional; off unless ENABLE_GOOGLE_SSO=true.
#
# Activation in the deployment environment:
#   pip install django-allauth
#   export ENABLE_GOOGLE_SSO=true
#   export GOOGLE_CLIENT_ID=...           # from Google Cloud Console
#   export GOOGLE_CLIENT_SECRET=...
#   export GOOGLE_SSO_ALLOWED_DOMAIN=     # empty = any Google account;
#                                         # e.g. "alleninstitute.org" to restrict
#   python manage.py migrate
#
# When enabled, any login-required page redirects straight to Google,
# auto-creates the account on first login, and grants full access.
# Authorized redirect URI to register with Google:
#   https://<your-host>/accounts/google/login/callback/
# ---------------------------------------------------------------------------
ENABLE_GOOGLE_SSO = os.environ.get('ENABLE_GOOGLE_SSO', 'false').lower() == 'true'
GOOGLE_SSO_ALLOWED_DOMAIN = os.environ.get('GOOGLE_SSO_ALLOWED_DOMAIN', '')

if ENABLE_GOOGLE_SSO:
    INSTALLED_APPS += [
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'allauth.socialaccount.providers.google',
    ]
    MIDDLEWARE += ['allauth.account.middleware.AccountMiddleware']
    SITE_ID = 1

    AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.ModelBackend',
        'allauth.account.auth_backends.AuthenticationBackend',
    ]

    SOCIALACCOUNT_PROVIDERS = {
        'google': {
            'APP': {
                'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
                'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                'key': '',
            },
            'SCOPE': ['profile', 'email'],
            'AUTH_PARAMS': {'access_type': 'online'},
        },
    }

    # One-click login, no email verification, auto-create account on first login.
    SOCIALACCOUNT_LOGIN_ON_GET = True
    SOCIALACCOUNT_AUTO_SIGNUP = True
    ACCOUNT_EMAIL_VERIFICATION = 'none'
    SOCIALACCOUNT_ADAPTER = 'ocs.adapters.DomainRestrictedSocialAdapter'

    # Send unauthenticated users straight to the Google login flow.
    LOGIN_URL = '/accounts/google/login/' 