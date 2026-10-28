#!/usr/bin/env bash
set -e

python manage.py migrate --noinput
mkdir -p /app/staticfiles
python manage.py collectstatic --noinput

exec "$@"
