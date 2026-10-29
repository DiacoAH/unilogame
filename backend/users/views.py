"""Internal API endpoints for bot↔backend communication."""

from __future__ import annotations

import hmac
import json
import logging
import os
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.models import Referral

logger = logging.getLogger(__name__)


def _check_internal_secret(request) -> bool:
    """Return True if the X-Internal-Secret header matches the configured secret."""
    expected = os.environ.get("INTERNAL_API_SECRET", "")
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Secret", "")
    return hmac.compare_digest(provided, expected)


@csrf_exempt
def internal_register_user(request):
    """Register the current bot user from a Telegram /start event.

    POST /api/internal/users/
    Header: X-Internal-Secret: <INTERNAL_API_SECRET>
    Body (JSON) or query params: { "telegram_id": 123 }

    On success returns 201 (newly created) or 200 (existing) JSON with
    id, telegram_id, created, and started_bot_at.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if not _check_internal_secret(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    # Best-effort body parsing: JSON body OR query params, never 500.
    data: dict = {}
    if request.body:
        try:
            parsed = json.loads(request.body)
            if isinstance(parsed, dict):
                data = parsed
            else:
                return JsonResponse({"error": "Invalid JSON body"}, status=400)
        except (json.JSONDecodeError, ValueError):
            pass  # fall through to query params

    if not data:
        data = parse_qs(request.META.get("QUERY_STRING", ""))
        data = {k: v[0] if v else v for k, v in data.items()}

    telegram_id = data.get("telegram_id")
    if telegram_id is None:
        return JsonResponse({"error": "telegram_id required"}, status=400)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid telegram_id"}, status=400)

    User = get_user_model()
    user, created = User.objects.get_or_create(telegram_id=telegram_id)

    if created or user.started_bot_at is None:
        user.started_bot_at = timezone.now()

    user.ensure_referral_code()
    user.save()

    # Best-effort referral attribution: invalid/missing/self/duplicate → log & ignore.
    referred_by = data.get("referred_by")
    if referred_by:
        try:
            referrer = User.objects.get(referral_code=referred_by)
        except User.DoesNotExist:
            logger.warning("referral: referrer code %r not found", referred_by)
        else:
            if referrer.telegram_id == user.telegram_id:
                logger.warning("referral: self-referral rejected for user %s", user.telegram_id)
            elif hasattr(user, 'referrals_received'):
                logger.info("referral: referee %s already has a referral; ignoring", user.telegram_id)
            else:
                Referral.objects.create(referrer=referrer, referee=user)

    return JsonResponse(
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "created": created,
            "started_bot_at": user.started_bot_at.isoformat()
            if user.started_bot_at
            else None,
            "referral_code": user.referral_code,
        },
        status=201 if created else 200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def internal_user_detail(request, telegram_id):
    """Get a user's referral code via internal API.

    GET /api/internal/users/<telegram_id>/
    Header: X-Internal-Secret: <INTERNAL_API_SECRET>

    Returns 403 without valid secret, 404 if user unknown, 405 for other methods.
    """
    if not _check_internal_secret(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        telegram_id = int(telegram_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid telegram_id"}, status=400)

    User = get_user_model()
    user = get_object_or_404(User, telegram_id=telegram_id)
    user.ensure_referral_code()
    user.save(update_fields=["referral_code"])
    return JsonResponse(
        {"telegram_id": user.telegram_id, "referral_code": user.referral_code}
    )
