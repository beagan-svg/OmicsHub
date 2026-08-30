"""Production-equivalent settings for the staging environment."""

import os

os.environ.setdefault("ENVIRONMENT", "staging")

from .prod import *  # noqa: E402, F403
