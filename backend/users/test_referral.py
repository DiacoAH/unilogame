"""Tests for the referral system."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client

from users.models import Referral

User = get_user_model()
INTERNAL_SECRET = "test-internal-secret"


def _create_user(telegram_id):
    """Create a user directly in the database."""
    return User.objects.create(telegram_id=telegram_id)


@pytest.mark.django_db
def test_referral_code_is_opaque():
    """Referral code is opaque, 12 chars, alphanumeric, and differs from telegram_id."""
    user = _create_user(12345)
    code = user.ensure_referral_code()
    assert code != str(user.telegram_id)
    assert len(code) == 12
    assert code.isalnum()


@pytest.mark.django_db
def test_valid_attribution_creates_referral():
    """POST with valid referral code creates a Referral (rewarded=False)."""
    referrer = _create_user(100)
    ref_code = referrer.ensure_referral_code()

    client = Client()
    response = client.post(
        "/api/internal/users/",
        {"telegram_id": 200, "referred_by": ref_code},
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code == 201
    assert Referral.objects.count() == 1
    referral = Referral.objects.get()
    assert referral.referrer == referrer
    assert referral.referee.telegram_id == 200
    assert referral.rewarded is False


@pytest.mark.django_db
def test_invalid_code_ignored_registration_still_succeeds():
    """Invalid referral code is ignored; user registration still succeeds."""
    client = Client()
    response = client.post(
        "/api/internal/users/",
        {"telegram_id": 201, "referred_by": "nonexistent"},
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code == 201
    assert Referral.objects.count() == 0


@pytest.mark.django_db
def test_self_referral_rejected():
    """Self-referral attempt is rejected; no Referral is created."""
    user = _create_user(300)
    ref_code = user.ensure_referral_code()

    client = Client()
    response = client.post(
        "/api/internal/users/",
        {"telegram_id": 300, "referred_by": ref_code},
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code in (200, 201)
    assert Referral.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_referee_ignored():
    """Referee with existing Referral keeps original referrer."""
    referrer1 = _create_user(100)
    referrer2 = _create_user(101)
    code2 = referrer2.ensure_referral_code()

    # Referee is registered with referrer1
    referee = _create_user(200)
    Referral.objects.create(referrer=referrer1, referee=referee)

    client = Client()
    response = client.post(
        "/api/internal/users/",
        {"telegram_id": 200, "referred_by": code2},
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code in (200, 201)
    assert Referral.objects.count() == 1
    referral = Referral.objects.get()
    assert referral.referrer == referrer1
    assert referral.referee == referee


@pytest.mark.django_db
def test_check_constraint_no_self_referral():
    """CheckConstraint prevents referrer == referee at the DB level."""
    user = _create_user(999)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Referral.objects.create(referrer=user, referee=user)


@pytest.mark.django_db
def test_detail_endpoint_returns_code():
    """GET detail endpoint generates and persists a referral code."""
    user = _create_user(500)
    assert user.referral_code is None

    client = Client()
    response = client.get(
        f"/api/internal/users/{user.telegram_id}/",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["referral_code"] is not None
    assert data["referral_code"] != ""

    user.refresh_from_db()
    assert user.referral_code is not None
    assert user.referral_code == data["referral_code"]


@pytest.mark.django_db
def test_detail_endpoint_404_unknown():
    """GET unknown telegram_id returns 404."""
    client = Client()
    response = client.get(
        "/api/internal/users/99999/",
        HTTP_X_INTERNAL_SECRET=INTERNAL_SECRET,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_endpoint_403_no_secret():
    """GET without X-Internal-Secret returns 403."""
    client = Client()
    response = client.get("/api/internal/users/500/")
    assert response.status_code == 403
