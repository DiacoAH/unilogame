# Space Game: Docker Infrastructure Spec

*Instructions for the coding agent. Implement exactly this structure. If something is ambiguous, pick the simpler option and note the choice in README.md.*

## 1. Goal and scope

Containerize the Space Game backend so the whole project runs with Docker Compose in development and in production.

**In scope:** PostgreSQL, Django (web), aiogram 3 bot, Nginx (reverse proxy, TLS, static files).

**Out of scope for now (do not add):** notifications, Celery, Redis, any scheduler or worker service, Kubernetes, CI/CD.

## 2. Architecture

```
Telegram app --HTTPS--> nginx :443 --HTTP--> web (Django + gunicorn :8000) --> db (PostgreSQL :5432)

bot (aiogram, long polling) --HTTPS, outbound only--> api.telegram.org
```

- Only nginx publishes ports to the host in production. db, web and bot are never published.
- The bot does **not** talk to Django or the database. Its only job: on /start, send a message with a button that opens the mini app. It needs only BOT\_TOKEN and WEBAPP\_URL.
- The bot uses long polling (no webhook), so nginx has no route for the bot.
- Telegram mini apps require HTTPS. Production needs a real domain and a TLS certificate; development uses a tunnel (Cloudflare Tunnel or ngrok) pointed at nginx.
- Assumption: the mini app frontend is served by Django (templates and static files). Do not build a separate JS frontend service.

## 3. Repository layout

```
spacegame/
  compose.yaml                 # base, shared by dev and prod
  compose.override.yaml        # dev, loaded automatically
  compose.prod.yaml            # prod, used with -f
  .env.example                 # committed; .env is not
  .gitignore                   # must include .env, backups/, staticfiles/
  Makefile
  README.md
  backend/
    Dockerfile
    docker-entrypoint.sh
    .dockerignore
    requirements.txt
    manage.py
    config/                    # Django project package (settings, urls, wsgi)
  bot/
    Dockerfile
    .dockerignore
    requirements.txt
    main.py
  nginx/
    dev.conf
    prod.conf.template
  scripts/
    init-letsencrypt.sh
    renew-certs.sh
    backup.sh
```

If a Django project already exists, keep its structure and adapt paths. The project package is assumed to be named config.

## 4. Services

### 4.1 db

- Image postgres:17-alpine (pin the major version).
- Named volume pgdata mounted at /var/lib/postgresql/data.
- Healthcheck with pg\_isready. Other services wait for service\_healthy.
- Credentials from env: POSTGRES\_DB, POSTGRES\_USER, POSTGRES\_PASSWORD.
- Dev: publish only on 127.0.0.1:5432. Prod: no published ports.

### 4.2 web (Django)

- Built from backend/Dockerfile: python:3.13-slim, pinned requirements (Django 5.2 LTS or newer stable, gunicorn, psycopg\[binary\], plus whatever the project needs), env vars PYTHONDONTWRITEBYTECODE=1 and PYTHONUNBUFFERED=1.
- Run as a non-root user. Create /app/staticfiles in the image and chown it to that user **before** switching user, so the shared static volume is writable.
- ENTRYPOINT is docker-entrypoint.sh (set -e): runs migrate --noinput, then collectstatic --noinput, then execs the container command. Only web runs migrations, never the bot.
- Default CMD (prod): gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -
- Dev command (compose.override.yaml): python manage.py runserver 0.0.0.0:8000 with ./backend bind-mounted at /app.
- Add a /healthz/ view returning HTTP 200 with body ok (no DB query).
- Healthcheck (the slim image has no curl), passing the URL as an argument so no inner quotes are needed: test: \['CMD', 'python', '-c', 'import sys,urllib.request; urllib.request.urlopen(sys.argv\[1\])', 'http://localhost:8000/healthz/'\]
- collectstatic writes into the shared named volume static (mounted at /app/staticfiles), which nginx mounts read-only.

**Django settings requirements (all env-driven):**

- SECRET\_KEY from DJANGO\_SECRET\_KEY. Fail at startup if it is missing and DEBUG is off.
- DEBUG from DJANGO\_DEBUG (default off).
- ALLOWED\_HOSTS from DJANGO\_ALLOWED\_HOSTS (comma-separated). Always also allow localhost and 127.0.0.1 (needed by the healthcheck).
- CSRF\_TRUSTED\_ORIGINS from DJANGO\_CSRF\_TRUSTED\_ORIGINS (comma-separated, with scheme).
- DATABASES: PostgreSQL, host db, port 5432, name/user/password from POSTGRES\_\*.
- SECURE\_PROXY\_SSL\_HEADER = ('HTTP\_X\_FORWARDED\_PROTO', 'https') and USE\_X\_FORWARDED\_HOST = True (Django sits behind nginx).
- When DEBUG is off: SESSION\_COOKIE\_SECURE = True and CSRF\_COOKIE\_SECURE = True. Do not enable HSTS yet.
- STATIC\_URL = '/static/', STATIC\_ROOT = BASE\_DIR / 'staticfiles'.
- Logging to the console (stdout) only.

**Telegram embedding (important):** Telegram Web and desktop clients show mini apps inside an iframe. Django's default X-Frame-Options: DENY would break that. Remove django.middleware.clickjacking.XFrameOptionsMiddleware and instead send a Content-Security-Policy header with frame-ancestors for Telegram (nginx adds it, see section 6). If session cookies are used inside the mini app they are third-party cookies in that iframe, so set SESSION\_COOKIE\_SAMESITE and CSRF\_COOKIE\_SAMESITE to 'None' (requires Secure). Do not implement Telegram initData validation now; that comes later.

### 4.3 bot (aiogram 3)

- Built from bot/Dockerfile: python:3.13-slim, non-root user, pinned requirements (aiogram 3.x only).
- Environment: BOT\_TOKEN and WEBAPP\_URL only. No database credentials, no Django secrets.
- Behavior: /start replies with a short welcome and an inline button (label Play) that opens WEBAPP\_URL as a web app. At startup also set the chat menu button to the same web app. Then run long polling. Log to stdout.
- No HTTP calls to the backend and no use of the requests library.
- Never run two instances with the same token at once (Telegram returns a conflict error). Use two separate bots in BotFather: one token for dev, one for prod.
- restart: unless-stopped.

Reference sketch for bot/main.py:

```python
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

WEBAPP_URL = os.environ['WEBAPP_URL']
bot = Bot(os.environ['BOT_TOKEN'])
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer('Welcome, commander! Open your solar system:', reply_markup=kb)


async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

### 4.4 nginx

- Image nginx:stable-alpine.
- Serves /static/ from the shared static volume (read-only). Proxies everything else to web:8000 with Host, X-Real-IP, X-Forwarded-For and X-Forwarded-Proto headers.
- client\_max\_body\_size 1m.
- Adds Content-Security-Policy: frame-ancestors for Telegram (see configs below).
- Dev: HTTP only, host port 8080. Prod: port 80 (ACME challenge and redirect to HTTPS) and port 443 (TLS).

## 5. Compose files

Use explicit environment lists (not env\_file) so each service receives only the variables it needs. Compose reads .env automatically for ${VAR} interpolation.

### compose.yaml (base)

```yaml
name: spacegame

services:
  db:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}']
      interval: 5s
      timeout: 3s
      retries: 10

  web:
    build: ./backend
    restart: unless-stopped
    environment:
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DJANGO_DEBUG: ${DJANGO_DEBUG:-0}
      DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS}
      DJANGO_CSRF_TRUSTED_ORIGINS: ${DJANGO_CSRF_TRUSTED_ORIGINS}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - static:/app/staticfiles
    healthcheck:
      test: ['CMD', 'python', '-c', 'import sys,urllib.request; urllib.request.urlopen(sys.argv[1])', 'http://localhost:8000/healthz/']
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  bot:
    build: ./bot
    restart: unless-stopped
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      WEBAPP_URL: ${WEBAPP_URL}

  nginx:
    image: nginx:stable-alpine
    restart: unless-stopped
    depends_on:
      web:
        condition: service_healthy
    volumes:
      - static:/var/www/static:ro

volumes:
  pgdata:
  static:
```

### compose.override.yaml (dev, loaded automatically by docker compose up)

```yaml
services:
  db:
    ports:
      - '127.0.0.1:5432:5432'

  web:
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DJANGO_DEBUG: '1'
    volumes:
      - ./backend:/app

  bot:
    volumes:
      - ./bot:/app

  nginx:
    ports:
      - '8080:80'
    volumes:
      - ./nginx/dev.conf:/etc/nginx/conf.d/default.conf:ro
```

### compose.prod.yaml (use with: docker compose -f compose.yaml -f compose.prod.yaml ...)

Using -f skips the automatic override file, so the dev settings do not leak into prod.

```yaml
services:
  nginx:
    ports:
      - '80:80'
      - '443:443'
    environment:
      DOMAIN: ${DOMAIN}
    volumes:
      - ./nginx/prod.conf.template:/etc/nginx/templates/default.conf.template:ro
      - certbot-www:/var/www/certbot:ro
      - letsencrypt:/etc/letsencrypt:ro

  certbot:
    image: certbot/certbot
    profiles: ['tools']
    volumes:
      - certbot-www:/var/www/certbot
      - letsencrypt:/etc/letsencrypt

volumes:
  certbot-www:
  letsencrypt:
```

The certbot service is on-demand only (profile tools), started with docker compose run --rm certbot ... and never by up.

## 6. Nginx configs

### nginx/dev.conf

In dev the traffic usually arrives through a tunnel that terminates HTTPS, so forward the tunnel's X-Forwarded-Proto header instead of nginx's own scheme.

```nginx
server {
    listen 80;
    client_max_body_size 1m;

    add_header Content-Security-Policy 'frame-ancestors https://web.telegram.org https://*.telegram.org' always;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    }
}
```

In dev, Django's runserver serves static files itself (DEBUG on), so no /static/ location is needed.

### nginx/prod.conf.template

The nginx image runs envsubst on files in /etc/nginx/templates, replacing only variables that exist in the container environment (so DOMAIN is replaced and nginx's own $host stays).

```nginx
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 1m;
    add_header Content-Security-Policy 'frame-ancestors https://web.telegram.org https://*.telegram.org' always;

    location /static/ {
        alias /var/www/static/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}
```

## 7. Environment variables

Commit .env.example, never .env.

```
# Django
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080

# PostgreSQL
POSTGRES_DB=spacegame
POSTGRES_USER=spacegame
POSTGRES_PASSWORD=change-me

# Bot
BOT_TOKEN=
WEBAPP_URL=https://your-tunnel-or-domain.example

# Production only
DOMAIN=game.example.com
LETSENCRYPT_EMAIL=you@example.com
```

- Dev with a tunnel: add the tunnel hostname to DJANGO\_ALLOWED\_HOSTS and its https URL to DJANGO\_CSRF\_TRUSTED\_ORIGINS, and set WEBAPP\_URL to the tunnel URL. Point the tunnel at http://localhost:8080.
- Prod: DJANGO\_DEBUG=0, DJANGO\_ALLOWED\_HOSTS=DOMAIN, DJANGO\_CSRF\_TRUSTED\_ORIGINS=https://DOMAIN, WEBAPP\_URL=https://DOMAIN, and a strong random secret key and database password.

## 8. TLS (production)

Nginx must have a certificate to start its 443 block, but certbot needs nginx on port 80 to get one. Solve this in scripts/init-letsencrypt.sh:

1. Create a temporary self-signed certificate at /etc/letsencrypt/live/$DOMAIN/ in the letsencrypt volume.
2. Start nginx (docker compose -f compose.yaml -f compose.prod.yaml up -d nginx).
3. Delete the temporary certificate and request the real one with certbot (webroot mode, webroot /var/www/certbot, --email $LETSENCRYPT\_EMAIL, --agree-tos, -d $DOMAIN). Support a --staging flag that uses the Let's Encrypt staging server, to avoid rate limits while testing.
4. Reload nginx (nginx -s reload via docker compose exec).

Renewal: scripts/renew-certs.sh runs certbot renew (webroot mode) and then reloads nginx. It is meant to be run daily by host cron. Document the cron line in README.md.

## 9. Backups

scripts/backup.sh runs pg\_dump inside the db container (docker compose exec -T db), gzips the output into backups/ with the date in the file name, and deletes backups older than 14 days. It is meant to be run daily by host cron. Document the restore command in README.md. A named volume is not a backup.

## 10. Makefile targets

up, down, build, logs, ps, migrate, superuser (createsuperuser), shell (Django shell), psql, plus prod-up, prod-down and prod-logs that use the -f compose.yaml -f compose.prod.yaml form.

## 11. Rules for the agent

- No secrets in git or in image layers. Provide .dockerignore files for backend and bot (exclude .git, .env, **pycache**, node\_modules, local venvs, backups).
- Pin image tags and Python dependency versions.
- All app containers run as non-root.
- In production, publish only ports 80 and 443 (nginx).
- Do not add Redis, Celery, a notifier, or any other service.
- Do not give the bot access to the database or to Django.
- Keep the README short: how to start dev, how to start prod, how to get the first certificate, cron lines, backup and restore.

## 12. Acceptance criteria

1. cp .env.example .env and docker compose up --build starts db, web, bot and nginx with no errors, and db becomes healthy before web starts.
2. http://localhost:8080/healthz/ returns ok through nginx.
3. The Django admin loads with working CSS.
4. Data survives docker compose down and up. docker compose down -v wipes it (state this in the README).
5. The bot answers /start with a Play button that opens WEBAPP\_URL (in dev, the tunnel URL), and the mini app loads inside Telegram, including Telegram Web.
6. Prod: the stack starts with the prod compose files, HTTP redirects to HTTPS, the certificate is valid, and docker compose ps shows only ports 80 and 443 published.
7. Stopping web does not crash the bot, and the other way around.
8. docker compose exec web id shows a non-root user.
9. Migrations run only from web, and re-running up is idempotent.

## 13. Later (do not implement now)

- Telegram initData validation in Django for mini app requests.
- Notifications: Django will call the Telegram Bot API directly, driven by a small notifier service. Not part of this task.
- Webhook mode for the bot, if polling ever becomes a problem.
