import os
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
DDL = ROOT / "compose" / "pg-init" / "sources.sql"
DECIMALS = {"observed_avg_price": 4, "gst": 4}


@dataclass(frozen=True)
class Table:
    source: str
    name: str
    workbook: str
    sheet: str
    interface: str
    provenance: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.source}.{self.name}"


TABLES = (
    Table("sales", "sales_lines", "01_Sales_Operational", "Sales_Lines", "db", "original"),
    Table("crm", "customers", "02_CRM_Customers", "Customers", "db", "original"),
    Table("erp", "product_costs", "04_Finance_Costs", "Product_Costs", "db"),
    Table("campaign", "campaigns", "03_Marketing_Campaigns", "Campaigns", "api"),
    Table("campaign", "targets", "03_Marketing_Campaigns", "Targets", "api"),
    Table("campaign", "attribution", "03_Marketing_Campaigns", "Attribution", "api"),
    Table("promotion", "coupon_plan", "03_Marketing_Campaigns", "Coupon_Plan", "api", "original"),
    Table("spend", "campaign_spend", "04_Finance_Costs", "Campaign_Spend", "api"),
    Table("spend", "daily_spend", "04_Finance_Costs", "Daily_Spend", "csv", "original"),
    Table("spend", "spend_recon", "04_Finance_Costs", "Spend_Recon", "csv", "synthetic"),
    Table("tax", "tax_rates", "04_Finance_Costs", "Tax_Rates", "csv", "original"),
)
SOURCES = tuple(dict.fromkeys(t.source for t in TABLES))


def snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower().replace("__", "_")


@cache
def workbook(name: str) -> dict[str, pd.DataFrame]:
    return pd.read_excel(DATA / f"{name}.xlsx", sheet_name=None)


def frame(table: Table) -> pd.DataFrame:
    df = workbook(table.workbook)[table.sheet].copy()
    df.columns = [snake(c) for c in df.columns]
    for column in df.select_dtypes("float").columns:
        df[column] = df[column].round(DECIMALS.get(column, 2))
    if table.provenance:
        df["provenance"] = table.provenance
    else:
        df["provenance_note"] = df.pop("provenance")
        synthetic = df["provenance_note"].str.upper().str.contains("SYNTHETIC")
        df.insert(len(df.columns) - 1, "provenance", synthetic.map({True: "synthetic", False: "original"}))
    return df


def native(row: tuple) -> list:
    return [v.item() if hasattr(v, "item") else v for v in row]


def bump_versions(conn) -> dict[str, int]:
    versions = {}
    for source in SOURCES:
        versions[source] = conn.execute(
            """
            INSERT INTO meta.source_versions (source, version) VALUES (%s, 1)
            ON CONFLICT (source) DO UPDATE SET version = meta.source_versions.version + 1
            RETURNING version
            """,
            (source,),
        ).fetchone()[0]
    return versions


def write_table(conn, table: Table, df: pd.DataFrame) -> None:
    conn.execute(f"TRUNCATE {table.qualified}")
    with conn.cursor().copy(f"COPY {table.qualified} ({', '.join(df.columns)}) FROM STDIN") as copy:
        for row in df.itertuples(index=False):
            copy.write_row(native(row))


def write_file(s3, bucket: str, table: Table, df: pd.DataFrame, version: int) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=f"{table.source}/{table.name}.csv",
        Body=df.to_csv(index=False).encode(),
        ContentType="text/csv",
        Metadata={"source-version": str(version)},
    )


def seed() -> dict[str, int]:
    import boto3
    import psycopg

    frames = {table: frame(table) for table in TABLES}
    with psycopg.connect(os.environ["SOURCES_DB_DSN"]) as conn:
        conn.execute(DDL.read_text())
        versions = bump_versions(conn)
        for table, df in frames.items():
            if table.interface != "csv":
                write_table(conn, table, df)
    bucket = os.environ.get("SOURCES_BUCKET", "sources")
    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], region_name="us-east-1")
    if bucket not in [b["Name"] for b in s3.list_buckets()["Buckets"]]:
        s3.create_bucket(Bucket=bucket)
    for table, df in frames.items():
        if table.interface == "csv":
            write_file(s3, bucket, table, df, versions[table.source])
    return versions


if __name__ == "__main__":
    print(seed())
