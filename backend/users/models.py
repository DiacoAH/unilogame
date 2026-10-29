from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # telegram_id is the only stable identifier; username is optional and not unique.
    username = models.CharField(max_length=150, blank=True, null=True)

    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    language_code = models.CharField(max_length=10, blank=True)
    is_premium = models.BooleanField(default=False)

    # bot / lifecycle tracking
    started_bot_at = models.DateTimeField(null=True, blank=True)
    first_app_open_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # notifications
    notifications_enabled = models.BooleanField(default=True)
    bot_blocked = models.BooleanField(default=False)

    USERNAME_FIELD = "telegram_id"
    REQUIRED_FIELDS = []
