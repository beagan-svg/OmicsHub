"""
URL configuration for viewer app.
This file forwards to the core/urls.py file to maintain compatibility 
with the existing Django project configuration.
"""

from django.urls import path, include

# Forward to the core URLs
urlpatterns = [
    path('', include('viewer.core.urls')),
] 