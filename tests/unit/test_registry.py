import pytest

from fabric_control import RegistryError, load_registry

ENTRY = """
  - dataset_id: {id}
    om_fqn: lake.{id}
    openlineage: {{namespace: s3://lake, name: {id}}}
    job_id: {id}
    tags: []
"""


def write(path, *ids):
    path.write_text("datasets:" + "".join(ENTRY.format(id=i) for i in ids) if ids else "datasets: []\n")


def test_merges_fragments(tmp_path):
    write(tmp_path / "a.yml", "unified/orders")
    write(tmp_path / "b.yml", "unified/customers")
    write(tmp_path / "c.yml")
    assert set(load_registry(tmp_path)) == {"unified/orders", "unified/customers"}


def test_duplicate_dataset_id_fails(tmp_path):
    write(tmp_path / "a.yml", "unified/orders")
    write(tmp_path / "b.yml", "unified/orders")
    with pytest.raises(RegistryError, match="duplicate"):
        load_registry(tmp_path)


def test_missing_field_fails(tmp_path):
    (tmp_path / "a.yml").write_text("datasets:\n  - dataset_id: unified/orders\n")
    with pytest.raises(RegistryError, match="missing"):
        load_registry(tmp_path)


def test_repo_registry_loads():
    assert isinstance(load_registry(), dict)
