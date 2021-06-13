from enum import Enum

from dask.dataframe import DataFrame, read_csv, read_parquet


class DataFormat(Enum):
    """Supported data formats."""

    CSV = "csv"
    PARQUET = "parquet"


def load_data(source: str, format: DataFormat) -> DataFrame:
    """Loads data from a local or remote source.

    Args:
        source: Source URI
        format: Data format

    Returns:
        Dask Dataframe loaded from the source.
    """
    if format == DataFormat.CSV:
        return read_csv(source)
    elif format == DataFormat.PARQUET:
        return read_parquet(source)
    else:
        raise RuntimeError(f"Unsupported data format {format}.")
