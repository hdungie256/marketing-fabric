COMPOSE := docker compose -f compose/docker-compose.yml
JOBS := $(COMPOSE) run --rm fabric-jobs
DEV := $(COMPOSE) --profile tools run --rm --build dev

.PHONY: up up-dev up-benchmark down bootstrap seed test test-jobs test-e2e test-e2e-full test-e2e-app format lint migrate break-dq fix-dq reset demo-ready

compose/.env:
	cp compose/.env.example $@

up: compose/.env
	$(COMPOSE) --profile core up -d --build

up-dev: compose/.env
	FABRIC_CONTROL_MODE=offline APP_DATA_MODE=fixture $(COMPOSE) --profile dev up -d --build

up-benchmark: compose/.env
	$(COMPOSE) --profile benchmark up -d --build

down:
	$(COMPOSE) --profile core --profile dev --profile benchmark down

bootstrap:
	$(COMPOSE) --profile core run --rm --build bootstrap

seed:
	$(JOBS) python -m sources.seed

test: compose/.env
	$(DEV) python -m pytest -p no:cacheprovider $(ARGS)

test-jobs:
	$(JOBS) python -m pytest -p no:cacheprovider tests/unit $(ARGS)

test-e2e:
	$(JOBS) env FABRIC_E2E=1 python -m pytest -p no:cacheprovider tests/e2e tests/reconcile $(ARGS)

test-e2e-full:
	$(JOBS) env FABRIC_E2E=1 FABRIC_E2E_FULL=1 python -m pytest -p no:cacheprovider tests/e2e tests/reconcile $(ARGS)

test-e2e-app:
	$(COMPOSE) exec streamlit env FABRIC_E2E=1 python -m pytest -p no:cacheprovider tests/e2e/test_br01_app.py $(ARGS)

format: compose/.env
	$(DEV) sh -c "ruff format . && ruff check --fix ."

lint: compose/.env
	$(DEV) sh -c "ruff format --check . && ruff check ."

migrate:
	$(JOBS) python -c "import fabric_control as fc; fc.run_migrations(); fc.sync_tags(); fc.sync_policies(); fc.verify_policies()"

break-dq:
	$(JOBS) python -c "from fabric_control.data_quality import break_dq; break_dq('$(DATASET)')"

fix-dq:
	$(JOBS) python -c "from fabric_control.data_quality import break_dq; break_dq('$(DATASET)', on=False)"

reset:
	$(COMPOSE) --profile core --profile dev --profile benchmark down -v
	$(MAKE) up

demo-ready:
	@echo "demo-ready: not implemented" && exit 1
