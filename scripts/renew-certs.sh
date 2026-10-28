#!/usr/bin/env bash
set -euo pipefail

docker compose run --rm certbot renew --webroot -w /var/www/certbot --agree-tos
docker compose -f compose.yaml -f compose.prod.yaml exec nginx nginx -s reload
