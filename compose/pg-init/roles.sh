#!/bin/bash
set -euo pipefail

login() {
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -v name="$1" -v password="$2" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'name') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'name') \gexec
ALTER ROLE :"name" PASSWORD :'password';
GRANT :"name" TO serving_user;
SQL
}

login marketing_analyst "$MARKETING_ANALYST_DB_PASSWORD"
login crm_marketing "$CRM_MARKETING_DB_PASSWORD"
login marketing_manager "$MARKETING_MANAGER_DB_PASSWORD"
login finance_controller "$FINANCE_CONTROLLER_DB_PASSWORD"
login data_steward "$DATA_STEWARD_DB_PASSWORD"
login data_ops "$DATA_OPS_DB_PASSWORD"
login app_writer "$APP_WRITER_DB_PASSWORD"
login ops_writer "$OPS_WRITER_DB_PASSWORD"
