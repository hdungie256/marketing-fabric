PYTHON ?= python3
COMPOSE := docker compose -f compose/docker-compose.yml
JOBS := $(COMPOSE) run --rm fabric-jobs

.PHONY: up up-dev down test migrate reset demo-ready

up:
	$(COMPOSE) --profile core up -d --build

up-dev:
	FABRIC_CONTROL_MODE=offline $(COMPOSE) --profile dev up -d --build

down:
	$(COMPOSE) --profile core --profile dev down

test:
	$(PYTHON) -m pytest

migrate:
	$(JOBS) python -c "import fabric_control as fc; fc.run_migrations(); fc.sync_tags(); fc.sync_policies()"

reset:
	$(COMPOSE) --profile core --profile dev down -v
	$(MAKE) up

demo-ready:
	@echo "demo-ready: not implemented" && exit 1
