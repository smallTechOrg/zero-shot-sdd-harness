import duckdb
from src.config import get_settings


def get_duckdb_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = get_settings().duckdb_path
    return duckdb.connect(path, read_only=read_only)
