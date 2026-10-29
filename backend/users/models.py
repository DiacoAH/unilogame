from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager
from django.db import models


class UserManager(UserManager):
    use_in_migrations = True

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        # Django's createsuperuser command passes the USERNAME_FIELD value
        # (telegram_id) as a keyword argument, but UserManager.create_superuser
        # expects 'username' as the first positional argument. Map it.
        user_model = self.model
        username_field = user_model.USERNAME_FIELD
        if username is None:
            username = extra_fields.pop(username_field, None)
        if username is None:
            raise TypeError(
                f"create_superuser() missing 1 required positional argument: '{username_field}'"
            )
        extra_fields[username_field] = username
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(username, email, password, **extra_fields)


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

    objects = UserManager()

    def __str__(self) -> str:
        return str(self.telegram_id)
