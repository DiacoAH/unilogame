FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m -s /bin/bash -u 1000 appuser && \
    mkdir -p /app/staticfiles && chown appuser:appuser /app/staticfiles

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY --chown=appuser:appuser . .
RUN chmod +x /app/docker-entrypoint.sh

USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
