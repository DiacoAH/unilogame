import logging
import secrets
import string

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager
from django.db import IntegrityError, models

logger = logging.getLogger(__name__)

_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 12


def _make_code() -> str:
    """Generate a random opaque referral code (12 alphanumeric chars)."""
    return ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


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

    # referrals
    referral_code = models.CharField(
        max_length=16, unique=True, null=True, blank=True, db_index=True
    )

    USERNAME_FIELD = "telegram_id"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self) -> str:
        return str(self.telegram_id)

    def ensure_referral_code(self) -> str:
        """Ensure this user has a referral code, generating one if missing.

        The code is opaque and never equals the telegram_id. Retries on
        collision (astronomically unlikely with 12 alphanumeric chars).
        """
        if self.referral_code:
            return self.referral_code
        for _ in range(10):
            code = _make_code()
            self.referral_code = code
            try:
                self.save(update_fields=['referral_code'])
                return code
            except IntegrityError:
                self.referral_code = None
                continue
        raise RuntimeError("Could not generate unique referral code after 10 attempts")


class Referral(models.Model):
    """Tracks who referred whom.

    Immutable one-referrer-per-referee: the referee ForeignKey is unique,
    so at most one Referral can exist per referee.
    """

    referrer = models.ForeignKey(
        User, related_name='referrals_given', on_delete=models.CASCADE
    )
    referee = models.OneToOneField(
        User, related_name='referrals_received', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    rewarded = models.BooleanField(default=False)
    rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(referrer=models.F('referee')),
                name='referral_no_self_referral',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.referrer} → {self.referee}'
