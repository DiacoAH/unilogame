"""Middleware that authenticates requests via Telegram Mini App initData."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from .auth import TmaValidationError, ensure_user_from_tma, validate_init_data


class TmaAuthenticationMiddleware:
    """Authenticate users via the ``Authorization: tma <initData>`` header.

    Place **after** ``AuthenticationMiddleware`` in settings.MIDDLEWARE.

    - Header missing or non-tma: leave request.user untouched (defaults
      to AnonymousUser set by AuthenticationMiddleware, or a session user
      for admin).
    - Header ``tma <initData>``: validate initData. On success, set
      request.user to the TMA user and skip CSRF. On failure, return 401.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("tma "):
            init_data = auth_header[4:]
            try:
                payload = validate_init_data(init_data)
            except TmaValidationError:
                return HttpResponse(status=401)

            request.user = ensure_user_from_tma(payload)
            request._dont_enforce_csrf_checks = True

        return self.get_response(request)
