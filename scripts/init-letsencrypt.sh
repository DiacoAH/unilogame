#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:?DOMAIN is required}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL is required}"
STAGING=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staging) STAGING=--staging; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

LIVE_DIR="/etc/letsencrypt/live/${DOMAIN}"

# 1. Temporary self-signed cert so nginx can start
mkdir -p "$LIVE_DIR"
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout "$LIVE_DIR/privkey.pem" \
  -out "$LIVE_DIR/fullchain.pem" \
  -subj "/CN=${DOMAIN}" >/dev/null 2>&1

# 2. Start nginx
docker compose -f compose.yaml -f compose.prod.yaml up -d nginx

# 3. Request real cert (webroot)
rm -rf "$LIVE_DIR"
docker compose run --rm certbot certonly --webroot \
  -w /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  $STAGING \
  -d "$DOMAIN"

# 4. Reload nginx
docker compose -f compose.yaml -f compose.prod.yaml exec nginx nginx -s reload
