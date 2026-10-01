from fabric_control.config import stub


def sync_policies() -> None:
    stub("sync_policies")


def verify_policies() -> None:
    stub("verify_policies")


def can_export(dataset_id: str, role: str) -> tuple[bool, str]:
    return stub("can_export", (False, "not implemented"), dataset_id=dataset_id, role=role)
