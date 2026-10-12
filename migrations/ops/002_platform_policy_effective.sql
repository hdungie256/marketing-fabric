CREATE TABLE ops.policy_effective (
    role text NOT NULL,
    dataset_id text NOT NULL,
    "column" text NOT NULL,
    action text NOT NULL,
    PRIMARY KEY (role, dataset_id, "column")
);
