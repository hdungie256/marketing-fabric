import ast
from pathlib import Path

import pytest
import yaml

from pipelines.dags.job_graph import JobGraphError, job_graph, order

ROOT = Path(__file__).resolve().parents[2]


def project(tmp_path, jobs: dict[str, dict]) -> Path:
    (tmp_path / "contracts" / "datasets").mkdir(parents=True)
    datasets = []
    for job_id, spec in jobs.items():
        datasets += [{"dataset_id": d, "job_id": job_id} for d in spec.get("outputs", [])]
        if spec.get("file", True):
            path = tmp_path / "pipelines" / "jobs" / job_id / "job.py"
            path.parent.mkdir(parents=True)
            path.write_text(f"INPUTS = {spec.get('inputs', [])!r}\nOUTPUTS = {spec.get('outputs', [])!r}\n")
    (tmp_path / "contracts" / "datasets" / "all.yml").write_text(yaml.safe_dump({"datasets": datasets}))
    return tmp_path


def test_dependencies_follow_inputs(tmp_path):
    root = project(
        tmp_path,
        {
            "ingest/sales": {"outputs": ["raw/sales/lines"]},
            "unified/orders": {"inputs": ["raw/sales/lines"], "outputs": ["unified/orders"]},
            "marts/shared/daily": {"inputs": ["unified/orders"], "outputs": ["mart_shared.daily"]},
        },
    )
    graph = job_graph(root)
    assert graph == {
        "ingest/sales": set(),
        "unified/orders": {"ingest/sales"},
        "marts/shared/daily": {"unified/orders"},
    }
    assert order(graph) == ["ingest/sales", "unified/orders", "marts/shared/daily"]


def test_unregistered_input_fails(tmp_path):
    root = project(tmp_path, {"unified/orders": {"inputs": ["raw/unknown"], "outputs": ["unified/orders"]}})
    with pytest.raises(JobGraphError, match="unregistered"):
        job_graph(root)


def test_registered_job_without_code_fails(tmp_path):
    root = project(tmp_path, {"unified/orders": {"outputs": ["unified/orders"], "file": False}})
    with pytest.raises(JobGraphError, match="has no"):
        job_graph(root)


def test_cycle_fails():
    with pytest.raises(JobGraphError, match="cycle"):
        order({"a": {"b"}, "b": {"a"}})


def test_repo_graph_has_every_ingest_job():
    graph = job_graph(ROOT)
    ingest = {f"ingest/{s}" for s in ("sales", "crm", "erp", "campaign", "promotion", "spend", "tax")}
    assert ingest <= set(graph)
    assert all(not graph[job] for job in ingest)


def test_partial_refresh_outranks_every_full_refresh_task():
    tree = ast.parse((ROOT / "pipelines" / "dags" / "partial_refresh.py").read_text())
    [call] = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "job_task"]
    options = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    assert options["weight_rule"] == "absolute"
    # under the default downstream rule a full_refresh task weighs at most its task count: jobs + 3 trailing tasks
    assert options["priority_weight"] > len(job_graph(ROOT)) + 3
