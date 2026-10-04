import fabric_control as fc
from fabric_control.clients import airflow

DAG_ID = "platform_smoke"


def test_trigger_runs_job_container_and_returns_xcom():
    run_id = fc.trigger(DAG_ID, {})
    assert airflow.wait(DAG_ID, run_id) == "success"
    assert airflow.xcom(DAG_ID, run_id, "check") == 3
