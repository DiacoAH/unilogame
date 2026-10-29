"""Internal API endpoints for bot↔backend communication."""

from __future__ import annotations

import hmac
import json
import os
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt


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
        user.save()

    return JsonResponse(
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "created": created,
            "started_bot_at": user.started_bot_at.isoformat()
            if user.started_bot_at
            else None,
        },
        status=201 if created else 200,
    )
