from django.http import HttpResponse


def healthz(request):
    """Minimal health check endpoint.

    Returns a 200 OK with body ``ok`` so the Docker Compose
    healthcheck and any external probe can confirm the web
    service is reachable and ready to serve requests.
    """
    return HttpResponse('ok')
