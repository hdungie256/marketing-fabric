"""Story 5.4: contact export locked without consent (FR-21, R12)."""

import fabric_control


def test_customer_datasets_export_locked_with_r12_reason():
    for dataset_id in ("mart_customer.rfm", "app.segments"):
        allowed, reason = fabric_control.can_export(dataset_id, "UG02")
        assert allowed is False
        assert reason == "Contact export disabled — no marketing consent data (R12)"


def test_lock_applies_to_every_role():
    for role in ("UG01", "UG02", "UG03", "UG04", "UG05", "UG06"):
        allowed, _ = fabric_control.can_export("mart_customer.rfm", role)
        assert allowed is False
