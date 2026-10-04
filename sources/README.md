# sources

Simulated source systems seeded from `data/*.xlsx` by `python -m sources.seed` (`make seed`).

| Source | Interface | Tables |
|---|---|---|
| sales | Postgres `sources.sales` | sales_lines |
| crm | Postgres `sources.crm` | customers |
| erp | Postgres `sources.erp` | product_costs |
| campaign | API `GET /campaign/<table>` | campaigns, targets, attribution |
| promotion | API `GET /promotion/coupon_plan` | coupon_plan |
| spend | API `GET /spend/campaign_spend`, CSV `sources/spend/*.csv` | campaign_spend, daily_spend, spend_recon (derived) |
| tax | CSV `sources/tax/tax_rates.csv` | tax_rates |

Each seed replaces the data and increments `meta.source_versions` per source; CSV files carry it as object metadata `source-version`. DDL lives in `compose/pg-init/sources.sql`.
