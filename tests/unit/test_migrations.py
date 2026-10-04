from fabric_control.migrations import migration_dirs, yoyo_url


def test_platform_first_and_empty_dirs_skipped(tmp_path):
    for name, has_sql in [("ops", True), ("_platform", True), ("app", False), ("mart_shared", True)]:
        (tmp_path / name).mkdir()
        if has_sql:
            (tmp_path / name / "001_x.sql").write_text("SELECT 1;")
    assert [d.name for d in migration_dirs(tmp_path)] == ["_platform", "mart_shared", "ops"]


def test_yoyo_url_uses_psycopg3():
    assert yoyo_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_repo_migrations_include_ops():
    assert "ops" in [d.name for d in migration_dirs()]
