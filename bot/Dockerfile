FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m -s /bin/bash -u 1000 appuser && \
    mkdir -p /app && chown appuser:appuser /app

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY --chown=appuser:appuser main.py .

USER appuser

CMD ["python", "main.py"]
