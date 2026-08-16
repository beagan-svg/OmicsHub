"""Load local settings for direct access or a VS Code port tunnel.

DEBUG and the host list are environment-driven rather than hardcoded, because the same
machine serves both cases: plain localhost during development, and a public tunnel URL
when others need to reach it. Turn DEBUG off for the tunnel because Django's error page shows
tracebacks, local variables, and settings to whoever opens the link.
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)
# Add the tunnel host (e.g. abc123-8000.usw2.devtunnels.ms) when forwarding a port.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
# The tunnel serves https on a different origin, so admin logins and any browsable-API
# POST need its origin trusted or Django rejects them as CSRF failures.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
