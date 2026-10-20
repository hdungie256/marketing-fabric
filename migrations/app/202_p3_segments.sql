-- depends: 000_create_schemas
CREATE TABLE app.segments (
    audience_id text NOT NULL,
    name text NOT NULL,
    criteria jsonb NOT NULL,
    customer_count integer NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (audience_id)
);
