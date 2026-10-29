"""Telegram Mini App (Web App) initData validation and user management.

Implements the server-side verification of Telegram's initData as described
in https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import datetime
from typing import Any
from urllib.parse import parse_qsl

from django.contrib.auth import get_user_model
from django.utils import timezone


class TmaValidationError(Exception):
    """Raised when Telegram Mini App initData fails validation."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def validate_init_data(
    init_data: str,
    bot_token: str | None = None,
    now: datetime.datetime | None = None,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    """Validate a Telegram Mini App initData string.

    Args:
        init_data: The raw query-string from the client (URL-encoded).
        bot_token: Bot token for HMAC computation. Defaults to ``BOT_TOKEN`` env.
        now: Current time for expiry check. Defaults to ``timezone.now()``.
        max_age_seconds: Max age of auth_data in seconds. Defaults to env or 3600.

    Returns:
        Dict with telegram_id, first_name, last_name, username,
        language_code, is_premium, and auth_date.

    Raises:
        TmaValidationError: On any validation failure (invalid_hash,
            expired, missing_hash, invalid_payload).
    """
    bot_token = bot_token or os.environ.get("BOT_TOKEN", "")
    max_age_seconds = max_age_seconds or int(
        os.environ.get("TMA_AUTH_DATE_MAX_AGE_SECONDS", "3600")
    )
    now = now or timezone.now()

    params = dict(parse_qsl(init_data, keep_blank_values=True))

    if "hash" not in params:
        raise TmaValidationError("Missing hash field", code="missing_hash")

    received_hash = params.pop("hash")

    # Build data_check_string: key=value sorted alphabetically by key, joined by \n
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )

    # secret_key = HMAC_SHA256(key=b"WebAppData", msg=BOT_TOKEN)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

    # calculated_hash = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TmaValidationError("Invalid hash", code="invalid_hash")

    # Validate auth_date
    auth_date_str = params.get("auth_date")
    if not auth_date_str:
        raise TmaValidationError("Missing auth_date", code="invalid_payload")

    try:
        auth_date = int(auth_date_str)
    except (ValueError, TypeError):
        raise TmaValidationError("Invalid auth_date", code="invalid_payload")

    auth_datetime = datetime.datetime.fromtimestamp(auth_date, tz=datetime.timezone.utc)
    age_seconds = (now - auth_datetime).total_seconds()
    if age_seconds > max_age_seconds:
        raise TmaValidationError("initData expired", code="expired")

    # Parse user field
    user_json = params.get("user")
    if not user_json:
        raise TmaValidationError("Missing user field", code="invalid_payload")

    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError:
        raise TmaValidationError("Invalid user JSON", code="invalid_payload")

    try:
        telegram_id = user_data["id"]
    except KeyError:
        raise TmaValidationError("Missing user id", code="invalid_payload")

    return {
        "telegram_id": telegram_id,
        "first_name": user_data.get("first_name"),
        "last_name": user_data.get("last_name"),
        "username": user_data.get("username"),
        "language_code": user_data.get("language_code", ""),
        "is_premium": user_data.get("is_premium", False),
        "auth_date": auth_date,
    }


def ensure_user_from_tma(payload: dict[str, Any]) -> Any:
    """Get or create a User from a validated initData payload.

    On create: set unusable password. On every call: refresh mutable
    fields from Telegram, update last_seen_at, and save.

    Args:
        payload: Dict returned by :func:`validate_init_data`.

    Returns:
        The User instance.
    """
    User = get_user_model()
    telegram_id = payload["telegram_id"]

    user, created = User.objects.get_or_create(telegram_id=telegram_id)

    if created:
        user.set_unusable_password()

    user.first_name = payload.get("first_name") or ""
    user.last_name = payload.get("last_name") or ""
    user.username = payload.get("username") or None
    user.language_code = payload.get("language_code", "") or ""
    user.is_premium = payload.get("is_premium", False)
    user.last_seen_at = timezone.now()
    user.save()

    return user
