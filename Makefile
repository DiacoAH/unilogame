.PHONY: up down build logs ps migrate superuser shell psql prod-up prod-down prod-logs

DEV_COMPOSE=docker compose -p unilogame-dev --env-file .env
PROD_COMPOSE=docker compose -p unilogame-prod --env-file .env.prod -f compose.yaml -f compose.prod.yaml

up:
	$(DEV_COMPOSE) up --build

down:
	$(DEV_COMPOSE) down

build:
	$(DEV_COMPOSE) build

logs:
	$(DEV_COMPOSE) logs -f

ps:
	$(DEV_COMPOSE) ps

migrate:
	$(DEV_COMPOSE) exec web python manage.py migrate

superuser:
	$(DEV_COMPOSE) exec web python manage.py createsuperuser

shell:
	$(DEV_COMPOSE) exec web python manage.py shell

psql:
	$(DEV_COMPOSE) exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

prod-up:
	$(PROD_COMPOSE) up --build

prod-down:
	$(PROD_COMPOSE) down

prod-logs:
	$(PROD_COMPOSE) logs -f
