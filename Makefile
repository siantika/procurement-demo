SHELL := /bin/bash
ENV_FILE ?= .env
export ENV_FILE
COMPOSE_FILES = -f compose.yaml
ifeq ($(ENV_FILE),.env)
COMPOSE_FILES += -f compose.local.yaml
endif
COMPOSE = docker compose $(COMPOSE_FILES) --env-file "$(ENV_FILE)"

.PHONY: start stop restart status logs check docker-start docker-stop \
	docker-restart docker-status docker-logs docker-seed docker-reset \
	docker-smoke docker-backup docker-preflight docker-preflight-vps

start:
	@bash scripts/dev-services.sh start

stop:
	@bash scripts/dev-services.sh stop

restart:
	@bash scripts/dev-services.sh restart

status:
	@bash scripts/dev-services.sh status

logs:
	@bash scripts/dev-services.sh logs

check:
	@uv run --env-file .env ruff check .
	@uv run --env-file .env python manage.py check
	@uv run --env-file .env python manage.py test

docker-preflight:
	@test -f "$(ENV_FILE)" || \
		(echo "File environment tidak ditemukan: $(ENV_FILE)" && false)
	@$(COMPOSE) config --quiet

docker-preflight-vps: docker-preflight
	@bash scripts/check-demo-env.sh "$(ENV_FILE)"

docker-start: docker-preflight
	@$(COMPOSE) up -d --build

docker-stop:
	@$(COMPOSE) down

docker-restart: docker-stop docker-start

docker-status:
	@$(COMPOSE) ps

docker-logs:
	@$(COMPOSE) logs --tail=200 -f

docker-seed:
	@$(COMPOSE) exec web python manage.py seed_demo

docker-reset:
	@$(COMPOSE) exec web python manage.py reset_demo_data \
		--confirm DEMO_ONLY

docker-smoke:
	@$(COMPOSE) exec web python manage.py smoke_demo --runs 3

docker-backup:
	@bash scripts/backup-demo.sh
