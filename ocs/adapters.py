"""allauth adapter for Google SSO.

Optionally restricts which Google accounts may sign in, based on the
GOOGLE_SSO_ALLOWED_DOMAIN setting (a comma-separated list of email domains).
An empty value accepts any Google account.
"""

from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpResponseForbidden


class DomainRestrictedSocialAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        domains = [d.strip().lower() for d in settings.GOOGLE_SSO_ALLOWED_DOMAIN.split(',') if d.strip()]
        if not domains:
            return  # any Google account is allowed
        email = (sociallogin.user.email or '').lower()
        if not any(email.endswith('@' + d) for d in domains):
            raise ImmediateHttpResponse(
                HttpResponseForbidden('Your Google account is not permitted to access this application.')
            )
