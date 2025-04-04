from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-development-key-change-this-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'prod_ocs',
        'USER': 'svc_bicore',
        'HOST': '/tmp',  # Unix socket directory
        'PORT': '5432',
        'OPTIONS': {
            'client_encoding': 'UTF8',
            'gssencmode': 'disable',  # This avoids the GSSAPI/Kerberos error
            'sslmode': 'disable'  # Disable SSL for local connections
        }
    }
}

# Debug toolbar settings
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
] 