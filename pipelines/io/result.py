import os
import pickle
from typing import Any


def write_result(value: Any) -> None:
    path = os.environ.get("FABRIC_RESULT_PATH")
    if path:
        with open(path, "wb") as f:
            pickle.dump(value, f)
