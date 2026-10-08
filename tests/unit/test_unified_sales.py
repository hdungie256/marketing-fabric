"""Story 1.6 transform tests: order key, gross math, shipping-once, mapping, first seen."""

import datetime
from decimal import Decimal

import pytest

from pipelines.jobs.unified import _common
from pipelines.jobs.unified.customers import transforms as customers_t
from pipelines.jobs.unified.order_lines import transforms as lines_t
from pipelines.jobs.unified.orders import transforms as orders_t
from pipelines.jobs.unified.product_cost import transforms as cost_t
from pipelines.jobs.unified.products import transforms as products_t
from pipelines.jobs.unified.ref_category_map import transforms as ref_t

pyspark_sql = pytest.importorskip("pyspark.sql")

SALES_SCHEMA = (
    "sales_line_id STRING, canonical_order_id STRING, transaction_date_iso DATE, customer_id LONG, "
    "transaction_id LONG, transaction_date STRING, product_sku STRING, product_description STRING, "
    "product_category STRING, quantity INT, avg_price DECIMAL(18,2), delivery_charges DECIMAL(18,2), "
    "coupon_status STRING, provenance STRING"
)
CRM_SCHEMA = "customer_id LONG, gender STRING, location STRING, tenure_months INT, provenance STRING"
COST_SCHEMA = (
    "product_sku STRING, product_category STRING, observed_avg_price DECIMAL(18,4), "
    "estimated_unit_cost DECIMAL(18,2), valid_from DATE, valid_through DATE, "
    "provenance STRING, provenance_note STRING"
)
MAPPING = {"Notebooks": "Notebooks & Journals"}


@pytest.fixture(scope="module")
def spark():
    session = pyspark_sql.SparkSession.builder.master("local[1]").appName("unified-1.6").getOrCreate()
    yield session
    session.stop()


@pytest.fixture(scope="module")
def sales(spark):
    rows = [
        (
            "L1",
            "C1",
            datetime.date(2019, 3, 1),
            1,
            100,
            "2019-03-01",
            "SKU-A",
            "Tee",
            "Apparel",
            2,
            Decimal("10.00"),
            Decimal("3.00"),
            "Used",
            "original",
        ),
        (
            "L2",
            "C1",
            datetime.date(2019, 3, 1),
            1,
            100,
            "2019-03-01",
            "SKU-B",
            "Mug",
            "Notebooks",
            1,
            Decimal("5.50"),
            Decimal("3.00"),
            "Not Used",
            "original",
        ),
        (
            "L3",
            "C2",
            datetime.date(2019, 5, 2),
            2,
            200,
            "2019-05-02",
            "SKU-C",
            "Nest Hub",
            "Nest-USA",
            3,
            Decimal("7.00"),
            Decimal("0.00"),
            "Clicked",
            "original",
        ),
    ]
    return spark.createDataFrame(rows, SALES_SCHEMA)


@pytest.fixture(scope="module")
def crm(spark):
    return spark.createDataFrame(
        [(1, "M", "Hanoi", 12, "original"), (2, "F", "HCMC", 6, "original"), (3, "F", "Danang", 3, "original")],
        CRM_SCHEMA,
    )


def test_order_key_format_and_gross_math(spark, sales):
    orders = {r.order_key: r for r in orders_t.build_orders(sales).collect()}
    assert set(orders) == {"1|100", "2|200"}
    assert abs(float(orders["1|100"].gross_value) - 25.50) < 1e-9
    assert abs(float(orders["2|200"].gross_value) - 21.00) < 1e-9


def test_shipping_counted_once_per_order(sales):
    orders = {r.order_key: r for r in orders_t.build_orders(sales).collect()}
    assert abs(float(orders["1|100"].shipping_fee) - 3.00) < 1e-9
    assert orders["1|100"].line_count == 2
    assert orders["2|200"].line_count == 1


def test_order_lines_keep_key_gross_and_mapping(sales):
    lines = {r.sales_line_id: r for r in lines_t.build_order_lines(sales, MAPPING).collect()}
    assert lines["L1"].order_key == "1|100"
    assert abs(float(lines["L1"].line_gross_value) - 20.00) < 1e-9
    assert lines["L2"].canonical_category == "Notebooks & Journals"
    assert lines["L1"].canonical_category == "Apparel"
    assert lines["L3"].canonical_category == "Nest-USA"


def test_customers_first_observed_and_order_count(spark, crm, sales):
    customers = {r.customer_id: r for r in customers_t.build_customers(crm, sales).collect()}
    assert customers[1].first_observed_order_date == datetime.date(2019, 3, 1)
    assert customers[2].first_observed_order_date == datetime.date(2019, 5, 2)
    assert customers[1].order_count == 1
    assert customers[3].first_observed_order_date is None
    assert customers[3].order_count == 0


def test_products_distinct_with_canonical(sales):
    products = {r.product_sku: r for r in products_t.build_products(sales, MAPPING).collect()}
    assert set(products) == {"SKU-A", "SKU-B", "SKU-C"}
    assert products["SKU-B"].canonical_category == "Notebooks & Journals"
    assert products["SKU-C"].canonical_category == "Nest-USA"


def test_product_cost_keeps_reference_and_canonical(spark):
    costs = spark.createDataFrame(
        [
            (
                "SKU-B",
                "Notebooks",
                Decimal("5.0000"),
                Decimal("2.50"),
                datetime.date(2019, 1, 1),
                datetime.date(2019, 12, 31),
                "synthetic",
                "estimated ref",
            )
        ],
        COST_SCHEMA,
    )
    row = cost_t.build_product_cost(costs, MAPPING).first()
    assert row.canonical_category == "Notebooks & Journals"
    assert abs(float(row.estimated_unit_cost) - 2.50) < 1e-9


def test_ref_map_materializes_mapping_file(spark, tmp_path):
    path = tmp_path / "category.yml"
    path.write_text("mappings:\n  - {raw: Notebooks, canonical: 'Notebooks & Journals', rule: synonym R13}\n")
    rows = _common.load_mapping_rows(path)
    assert [(r["raw_category"], r["canonical_category"]) for r in ref_t.build_map(spark, rows).collect()] == [
        ("Notebooks", "Notebooks & Journals")
    ]
