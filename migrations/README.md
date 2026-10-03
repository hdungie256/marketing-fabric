# migrations

Serving database migrations (yoyo). One folder per schema, files named `NNN_<slice>_<desc>.sql`.

Reserved numbers in shared schemas (`mart_shared`, `app`, `ops`):

| Slice | Range |
|---|---|
| platform | 001–099 |
| campaign | 100–199 |
| customer | 200–299 |
| finance | 300–399 |
