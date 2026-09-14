SHELL := /bin/bash

.PHONY: start stop restart status logs check

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
