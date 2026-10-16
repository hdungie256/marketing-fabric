-- depends: 000_create_schemas
CREATE TABLE IF NOT EXISTS app.exception_status (
    exception_id text PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('new', 'seen', 'accepted')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL
);
