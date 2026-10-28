#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="$(pwd)/backups"
mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/spacegame-$(date +%F).sql.gz"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"

find "$BACKUP_DIR" -name 'spacegame-*.sql.gz' -mtime +14 -delete

echo "Backup written to $FILE"
