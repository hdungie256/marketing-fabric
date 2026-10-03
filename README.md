# Marketing Data Fabric

Demo data platform for campaign intelligence.

## Setup

Python 3.11, pip ≥ 25.1.

```bash
cp compose/.env.example compose/.env
pip install --group dev
```

Docker Desktop memory ≥ 12GB.

## Commands

| Command | Action |
|---|---|
| `make up` | Start full stack |
| `make up-dev` | Start Postgres, SeaweedFS, Streamlit (offline) |
| `make down` | Stop stack |
| `make reset` | Delete volumes and restart |
| `make migrate` | Run migrations, sync tags and policies |
| `make test` | Run tests |
| `make format` | Format and fix lint |
| `make lint` | Check format and lint |

## Local URLs

| Service | URL |
|---|---|
| Streamlit | http://localhost:8501 |
| API | http://localhost:8000/docs |
| OpenMetadata | http://localhost:8585 |
| Airflow | http://localhost:8080 |
| SeaweedFS S3 | http://localhost:8333 |
| Postgres | localhost:5432 |

OpenMetadata login: `admin@open-metadata.org` / `admin`.
Airflow login: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` from `compose/.env`.

## Structure

```text
api/              Simulated Campaign, Coupon and Spend API
app/              Streamlit shell, pages, services, repositories
benchmark/        Benchmark profile work
compose/          Docker Compose, images, Postgres init
contracts/        Dataset registry, schemas, constants, fixtures
fabric_control/   Client for OpenMetadata, Airflow and Postgres admin
governance/       Glossary, tags, mappings
migrations/       Serving database migrations
pipelines/        DAGs, IO and jobs
scripts/          Repo checks
sources/          Source seeds and fault toggles
tests/            Unit, reconcile and e2e tests
```
