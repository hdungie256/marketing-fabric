CREATE TABLE ops.page_timings (
    timing_id bigserial PRIMARY KEY,
    page text NOT NULL,
    ms numeric(10,1) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
