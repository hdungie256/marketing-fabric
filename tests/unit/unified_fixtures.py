from fabric_control.contracts import columns, load_schema

CATEGORY_PAIRS = [
    ("Notebooks", "Notebooks & Journals"),
    ("Notebooks & Journals", "Notebooks & Journals"),
    ("Nest", "Nest"),
    ("Nest-USA", "Nest-USA"),
    ("Nest-Canada", "Nest-Canada"),
    ("Apparel", "Apparel"),
]


def contract(dataset_id):
    return columns(load_schema(dataset_id))


def frame(spark, dataset_id, rows):
    return spark.createDataFrame(rows, ", ".join(f"`{name}` {kind}" for name, kind in contract(dataset_id)))


def schema(df):
    return [(f.name, f.dataType.simpleString()) for f in df.schema.fields]


def category_map(spark, pairs=CATEGORY_PAIRS):
    return spark.createDataFrame(pairs, "source_category STRING, category STRING")
