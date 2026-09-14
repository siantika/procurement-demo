SHELL := /bin/bash
DEMO_ENV_FILE ?= .env.demo
export DEMO_ENV_FILE

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
	@test -f "$(DEMO_ENV_FILE)" || \
		(echo "File environment demo tidak ditemukan: $(DEMO_ENV_FILE)" && false)
	@docker compose config --quiet

docker-preflight-vps: docker-preflight
	@bash scripts/check-demo-env.sh "$(DEMO_ENV_FILE)"

docker-start: docker-preflight
	@docker compose up -d --build

docker-stop:
	@docker compose down

docker-restart: docker-stop docker-start

docker-status:
	@docker compose ps

docker-logs:
	@docker compose logs --tail=200 -f

docker-seed:
	@docker compose exec web python manage.py seed_demo

docker-reset:
	@docker compose exec web python manage.py reset_demo_data \
		--confirm DEMO_ONLY

docker-smoke:
	@docker compose exec web python manage.py smoke_demo --runs 3

docker-backup:
	@bash scripts/backup-demo.sh
