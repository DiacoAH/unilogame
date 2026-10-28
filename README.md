# Space Game

Docker-based backend: PostgreSQL + Django (gunicorn) + aiogram bot + Nginx reverse proxy.

## Prerequisites

- Docker compose (v2)
- `uv` available on host (optional; uv is installed inside the build context)

## Development

```bash
cp .env.example .env
make up
```

- Django runs on `localhost:8000` (inside the container), proxied by Nginx on `http://localhost:8080`.
- PostgreSQL is published on `127.0.0.1:5432` for local tools.
- Hot-reload: `./backend` and `./bot` are mounted as volumes, so edits apply without rebuilding.

```bash
make migrate          # run migrations
make superuser         # create admin user
make shell             # Django shell
make psql              # psql into the db
make logs              # tail logs
make down              # stop + remove containers (volumes persist)
```

## Production

```bash
make prod-up           # starts db, web, bot, nginx (no override)
make prod-down
make prod-logs
```

Production exposes only ports `80` and `443` (no `5432`/`8000`). The Nginx config is templated from `nginx/prod.conf.template` and rendered with the `DOMAIN` env var.

### TLS with Let's Encrypt

```bash
# First cert (use --staging to test against the staging issuance server)
scripts/init-letsencrypt.sh            # or: scripts/init-letsencrypt.sh --staging
```

This starts Nginx with a temporary self-signed cert, runs `certbot certonly` via the `webroot` plugin, then reloads Nginx.

### Renewal — add to crontab

```cron
0 3 * * *  cd /path/to/unilogame && scripts/renew-certs.sh
0 2 * * *  cd /path/to/unilogame && scripts/backup.sh
```

Both run against the currently-started prod stack.

## Backups

```bash
# Create
scripts/backup.sh          # writes backups/spacegame-YYYY-MM-DD.sql.gz

# Restore
zcat backups/spacegame-*.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"

# Prune (kept inside backup.sh: deletes files older than 14 days)
```

## Notes

- `docker compose down` removes containers but keeps the `pgdata` volume (data persists).
- `docker compose down -v` also removes named volumes — **wipes all data**, including the database.
- Re-running `make up` is idempotent: `docker-entrypoint.sh` runs `migrate` and `collectstatic --noinput`, both safe to repeat.
- `.env` is git-ignored; `.env.example` documents every variable.
