#!/bin/bash
set -euo pipefail
shopt -s nullglob

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" <<SQL
CREATE USER sources_user PASSWORD '$SOURCES_DB_PASSWORD';
CREATE DATABASE sources OWNER sources_user;
CREATE USER serving_user PASSWORD '$SERVING_DB_PASSWORD';
CREATE DATABASE serving OWNER serving_user;
SQL

for f in /pg-init/*.sql; do
  psql -v ON_ERROR_STOP=1 -U sources_user -d sources -f "$f"
done

bash /pg-init/roles.sh
