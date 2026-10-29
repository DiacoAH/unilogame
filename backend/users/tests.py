"""Unit tests for Telegram Mini App initData validation.

No database access required; all tests are pure functions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import datetime
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from users.auth import TmaValidationError, validate_init_data

TEST_BOT_TOKEN = "123456789:TestBotTokenAbCdEfGhIjKlMnOp"

TEST_USER = {
    "id": 123456789,
    "first_name": "Test",
    "last_name": "User",
    "username": "testuser",
    "language_code": "en",
    "is_premium": True,
}


def make_init_data(
    bot_token: str,
    *,
    hash_override: str | None = None,
    **params: str | int,
) -> str:
    """Build a valid (or intentionally-invalid) init_data query string for tests."""
    # data_check_string: sorted key=value pairs joined by \n
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_value = (
        hash_override
        or hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
    )
    params["hash"] = hash_value
    return urlencode(params)


@pytest.fixture
def fixed_now() -> datetime.datetime:
    return datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def valid_auth_date(fixed_now: datetime.datetime) -> int:
    return int((fixed_now - datetime.timedelta(minutes=5)).timestamp())


class TestValidateInitData:
    def test_valid_payload(self, fixed_now: datetime, valid_auth_date: int):
        params = {
            "auth_date": valid_auth_date,
            "user": json.dumps(TEST_USER),
            "query_id": "AAHdF6IQAAAAAN0XohD3N2NR",
        }
        init_data = make_init_data(TEST_BOT_TOKEN, **params)

        result = validate_init_data(
            init_data,
            bot_token=TEST_BOT_TOKEN,
            now=fixed_now,
            max_age_seconds=3600,
        )

        assert result["telegram_id"] == TEST_USER["id"]
        assert result["first_name"] == "Test"
        assert result["last_name"] == "User"
        assert result["username"] == "testuser"
        assert result["language_code"] == "en"
        assert result["is_premium"] is True
        assert result["auth_date"] == valid_auth_date

    def test_tampered_hash(self, fixed_now: datetime, valid_auth_date: int):
        params = {
            "auth_date": valid_auth_date,
            "user": json.dumps(TEST_USER),
        }
        init_data = make_init_data(
            TEST_BOT_TOKEN, hash_override="0" * 64, **params
        )

        with pytest.raises(TmaValidationError) as exc_info:
            validate_init_data(
                init_data,
                bot_token=TEST_BOT_TOKEN,
                now=fixed_now,
                max_age_seconds=3600,
            )

        assert exc_info.value.code == "invalid_hash"

    def test_expired_auth_date(self, fixed_now: datetime.datetime):
        # auth_date 2 hours ago → older than max_age_seconds (3600)
        auth_date = int((fixed_now - datetime.timedelta(hours=2)).timestamp())
        params = {
            "auth_date": auth_date,
            "user": json.dumps(TEST_USER),
        }
        init_data = make_init_data(TEST_BOT_TOKEN, **params)

        with pytest.raises(TmaValidationError) as exc_info:
            validate_init_data(
                init_data,
                bot_token=TEST_BOT_TOKEN,
                now=fixed_now,
                max_age_seconds=3600,
            )

        assert exc_info.value.code == "expired"

    def test_missing_hash(self, fixed_now: datetime, valid_auth_date: int):
        params = {
            "auth_date": valid_auth_date,
            "user": json.dumps(TEST_USER),
        }
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(params.items())
        )
        # No hash field at all
        init_data = urlencode(params)

        with pytest.raises(TmaValidationError) as exc_info:
            validate_init_data(
                init_data,
                bot_token=TEST_BOT_TOKEN,
                now=fixed_now,
                max_age_seconds=3600,
            )

        assert exc_info.value.code == "missing_hash"
