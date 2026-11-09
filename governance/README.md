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

A glossary term in `glossary/<slice>.yml` links one primary `column` of its `dataset_id`.
When the formula reads more columns of the same dataset, list them in `source_columns`:

```yaml
column: attributed_gross_value
source_columns: [allocated]
```

Every listed column must exist in the dataset's schema contract.
