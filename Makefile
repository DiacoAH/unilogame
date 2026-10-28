.PHONY: up down build logs ps migrate superuser shell psql prod-up prod-down prod-logs

COMPOSE=docker compose
PROD_COMPOSE=docker compose -f compose.yaml -f compose.prod.yaml

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec web python manage.py migrate

superuser:
	$(COMPOSE) exec web python manage.py createsuperuser

shell:
	$(COMPOSE) exec web python manage.py shell

psql:
	$(COMPOSE) exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

prod-up:
	$(PROD_COMPOSE) up --build

prod-down:
	$(PROD_COMPOSE) down

prod-logs:
	$(PROD_COMPOSE) logs -f
