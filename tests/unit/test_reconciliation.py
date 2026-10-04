from pipelines.jobs.ingest.reconciliation import Profile, load_baselines, reconcile


def test_matching_load_passes():
    check = reconcile("l1", "raw/a/b", Profile(3, "9"), Profile(3, "9"), 3)
    assert check.passed and check.reason is None


def test_row_count_mismatch_fails():
    check = reconcile("l1", "raw/a/b", Profile(3, "9"), Profile(2, "9"), None)
    assert not check.passed and "source 3 != raw 2" in check.reason


def test_checksum_mismatch_fails():
    check = reconcile("l1", "raw/a/b", Profile(3, "9"), Profile(3, "8"), None)
    assert not check.passed and "checksum" in check.reason


def test_baseline_mismatch_fails():
    check = reconcile("l1", "raw/a/b", Profile(3, "9"), Profile(3, "9"), 52924)
    assert not check.passed and "baseline 52924" in check.reason


def test_no_baseline_is_not_checked():
    assert reconcile("l1", "raw/a/b", Profile(3, "9"), Profile(3, "9"), None).passed


def test_load_baselines(tmp_path):
    path = tmp_path / "baselines.yml"
    path.write_text("load_rows:\n  raw/sales/sales_lines: 52924\n")
    assert load_baselines(path) == {"raw/sales/sales_lines": 52924}
    assert load_baselines(tmp_path / "missing.yml") == {}
