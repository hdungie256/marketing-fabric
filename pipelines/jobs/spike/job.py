import pickle
import sys

from pipelines.io import read_delta
from pipelines.io.spark import get_spark

OUTPUTS = []

if __name__ == "__main__":
    get_spark("spike")
    rows = read_delta("raw/spike/s3_delta").count()
    with open(sys.argv[1], "wb") as f:
        pickle.dump({"rows": rows}, f)
