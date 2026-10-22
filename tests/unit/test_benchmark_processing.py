import csv

from benchmark.processing import flink_job
from benchmark.processing.common import SEGMENTS
from benchmark.processing.data import OFFSET


def test_condition_translates_every_rule_operator():
    spec = {"r_max": 2, "f_in": [2, 3], "m_eq": 5, "any": [{"f_min": 4}, {"m_min": 4}]}
    assert flink_job.condition(spec) == (
        "recency_score <= 2 AND frequency_score IN (2, 3) AND monetary_score = 5 "
        "AND (frequency_score >= 4 OR monetary_score >= 4)"
    )
    assert flink_job.condition({}) == "TRUE"


def test_segment_case_keeps_yaml_order_and_last_rule_as_default():
    case = flink_job.segment_case()
    positions = [case.index(flink_job.literal(s["name"])) for s in SEGMENTS]
    assert positions == sorted(positions)
    assert case.endswith(f"ELSE {flink_job.literal(SEGMENTS[-1]['name'])} END")
    assert "'Can''t Lose'" in case  # quotes in segment names are escaped


def test_category_case_maps_synonyms_only():
    assert "WHEN 'Notebooks' THEN 'Notebooks & Journals'" in flink_job.category_case()
    assert "Nest" not in flink_job.category_case()


def test_copies_shift_ids_so_order_keys_stay_unique(tmp_path, monkeypatch):
    from benchmark.processing import data

    sales = (
        [
            "CustomerID",
            "Transaction_ID",
            "Transaction_Date_ISO",
            "Product_Category",
            "Quantity",
            "Avg_Price",
            "Delivery_Charges",
        ],
        [(17850, 16679, "2019-01-01", "Nest-USA", 1, 153.71, 6.5)],
    )
    crm = (["CustomerID", "Gender", "Location", "Tenure_Months"], [(17850, "M", "Chicago", 12)])
    monkeypatch.setattr(data, "rows", lambda path: sales if path == data.SALES else crm)
    data.build(tmp_path, 3)
    lines = list(csv.reader((tmp_path / "lines.csv").open()))
    assert [(int(r[0]), int(r[1])) for r in lines] == [(17850 + k * OFFSET, 16679 + k * OFFSET) for k in range(3)]
    assert lines[0][5:7] == ["153.71", "6.50"]
