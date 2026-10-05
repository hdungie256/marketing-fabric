import pandas as pd


def table(
    df: pd.DataFrame,
    *,
    dataset_id: str | None = None,
    campaign_col: str | None = None,
    formats: dict[str, str] | None = None,
) -> None:
    raise NotImplementedError("Story 1.12")
