PYTHON ?= python3
COMPOSE := docker compose -f compose/docker-compose.yml
JOBS := $(COMPOSE) run --rm fabric-jobs

.PHONY: up up-dev up-benchmark down bootstrap test test-e2e format lint migrate reset demo-ready

compose/.env:
	cp compose/.env.example $@

up: compose/.env
	$(COMPOSE) --profile core up -d --build

up-dev: compose/.env
	FABRIC_CONTROL_MODE=offline $(COMPOSE) --profile dev up -d --build

up-benchmark: compose/.env
	$(COMPOSE) --profile benchmark up -d --build

down:
	$(COMPOSE) --profile core --profile dev --profile benchmark down

bootstrap:
	$(COMPOSE) --profile core run --rm --build bootstrap

test:
	$(PYTHON) -m pytest

test-e2e:
	$(JOBS) env FABRIC_E2E=1 python -m pytest -p no:cacheprovider tests/e2e

format:
	ruff format .
	ruff check --fix .

lint:
	ruff format --check .
	ruff check .

migrate:
	$(JOBS) python -c "import fabric_control as fc; fc.run_migrations(); fc.sync_tags(); fc.sync_policies()"

reset:
	$(COMPOSE) --profile core --profile dev --profile benchmark down -v
	$(MAKE) up

demo-ready:
	@echo "demo-ready: not implemented" && exit 1
