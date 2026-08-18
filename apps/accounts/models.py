from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Store a project user who owns queue entries.

    Jobs are queued per user and the worker round-robins between users, so every queue
    entry needs a stable owner. Defined up front so fields can be added without the
    mid-project user-model migration.
    """

    # Dashboard column keys this user has chosen to see. Empty means the default set.
    # storing the choice here rather than in a session keeps it across logins and browsers.
    visible_columns = models.JSONField(default=list, blank=True)
    visible_location_columns = models.JSONField(default=list, blank=True)
    queue_paused = models.BooleanField(default=False)

    def __str__(self):
        return self.get_username()
