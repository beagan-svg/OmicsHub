"""
Production settings.

Inherits everything from base.py and overrides only what genuinely differs in
production: secrets, allowed hosts, the database, and security hardening. Every
environment-specific value is read from environment variables so nothing
sensitive lives in source control.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"The {name} environment variable must be set in production.")
    return value


DEBUG = False

SECRET_KEY = required_env('SECRET_KEY')

ALLOWED_HOSTS = required_env('ALLOWED_HOSTS').split(',')

# Needed for POST/CSRF when served over HTTPS behind a proxy, e.g.
# "https://ocs.example.org". Comma-separated.
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': required_env('DB_NAME'),
        'USER': required_env('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'CONN_HEALTH_CHECKS': True,
    }
}

# HTTPS hardening. Set USE_HTTPS=false only if TLS is terminated upstream
# without forwarding the X-Forwarded-Proto header.
USE_HTTPS = os.environ.get('USE_HTTPS', 'true').lower() == 'true'
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_SSL_REDIRECT = USE_HTTPS
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'INFO',
    },
}

(BASE_DIR / 'logs').mkdir(exist_ok=True)
