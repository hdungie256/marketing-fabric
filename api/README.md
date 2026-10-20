# api

Simulated Campaign, Coupon and Spend API (FastAPI).

| Method | Path | Notes |
|---|---|---|
| GET | `/{source}/{table}` | Rows plus `source_version` |
| PUT | `/spend/campaign_spend/{campaign_id}/{date}` | Body `{"allocated_online_spend": n}`, header `X-Fabric-Role`. Only roles under `edit:` in `governance/access_matrix.yml`. Bumps `source_version` and triggers `partial_refresh` |
