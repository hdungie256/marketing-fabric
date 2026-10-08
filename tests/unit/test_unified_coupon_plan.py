import hashlib
from datetime import UTC, datetime

import pytest

from pipelines.jobs.unified.coupon_plan import transforms
from tests.unit.unified_fixtures import category_map, contract, frame, schema

pytest.importorskip("pyspark.sql")

NOTEBOOKS = [("Jan", "Notebooks", "NOTES10", 10, "original"), ("Jan", "Notebooks & Journals", "NJ10", 10, "original")]
AT = datetime(2026, 10, 5, tzinfo=UTC)


def split(spark, rows):
    return transforms.transform(frame(spark, "raw/promotion/coupon_plan", rows), category_map(spark))


def test_outputs_match_contracts(spark):
    kept, dropped = split(spark, NOTEBOOKS)
    assert schema(kept) == contract("unified/coupon_plan")
    assert schema(transforms.exceptions(dropped, kept, AT)) == contract("unified/exceptions_coupon_plan_duplicate")


@pytest.mark.parametrize(("name", "number"), [("Jan", 1), ("Dec", 12), (" jan", 1), ("JUN", 6), ("Janvier", None)])
def test_month_number(spark, name, number):
    df = spark.createDataFrame([(name,)], "month STRING")
    assert transforms.month_number(df).collect()[0].month == number


def test_duplicate_keeps_row_already_using_the_standard_name(spark):
    kept, dropped = split(spark, NOTEBOOKS)
    assert [(r.month, r.product_category, r.coupon_code, r.source_category) for r in kept.collect()] == [
        (1, "Notebooks & Journals", "NJ10", "Notebooks & Journals")
    ]
    assert [r.coupon_code for r in dropped.collect()] == ["NOTES10"]


def test_input_order_does_not_change_the_kept_row(spark):
    kept, _ = split(spark, list(reversed(NOTEBOOKS)))
    assert [r.coupon_code for r in kept.collect()] == ["NJ10"]


def test_ties_without_standard_name_keep_smallest_code(spark):
    rows = [("Feb", "Notebooks", "NOTES20", 20, "original"), ("Feb", "Notebooks", "NOTES02", 20, "original")]
    kept, _ = split(spark, rows)
    assert [r.coupon_code for r in kept.collect()] == ["NOTES02"]


def test_unique_rows_produce_no_exceptions(spark):
    kept, dropped = split(
        spark, [("Jan", "Nest", "NEST10", 10, "original"), ("Jan", "Nest-USA", "ELEC10", 10, "original")]
    )
    assert kept.count() == 2 and dropped.count() == 0


def test_exception_row_is_stable(spark):
    kept, dropped = split(spark, NOTEBOOKS)
    first = transforms.exceptions(dropped, kept, AT).collect()[0]
    again = transforms.exceptions(*reversed(split(spark, list(reversed(NOTEBOOKS)))), datetime(2027, 1, 1, tzinfo=UTC))
    natural_key = "1|Notebooks & Journals|NOTES10"
    assert first.natural_key == natural_key
    assert first.exception_id == hashlib.sha1(f"coupon_plan_duplicate|{natural_key}".encode()).hexdigest()
    assert first.exception_id == again.collect()[0].exception_id
    assert (first["class"], first.dataset_id) == ("coupon_plan_duplicate", "unified/coupon_plan")
    assert first.detail == "source_category=Notebooks; kept coupon_code=NJ10"
