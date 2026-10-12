# governance

Glossary, tags, access policy and reference mappings as code.

Tag a serving column in your slice's `tags/<slice>.yml`:

```yaml
columns:
  mart_shared.campaign_attributed_orders:
    customer_id: Sensitivity.direct_identifier
```

Give a tag its actions per role (`allow`, `mask:partial`, `deny`; missing means `deny`):

```yaml
actions: {default: 'mask:partial', UG02: allow}
```

List who can read a dataset in `access_matrix.yml`. Then run `make migrate`.
