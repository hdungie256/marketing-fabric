from typing import Protocol

import pandas as pd


class DataSource(Protocol):
    def read(self, dataset_id: str) -> pd.DataFrame: ...


def current_source() -> DataSource:
    raise NotImplementedError("Story 1.11")
