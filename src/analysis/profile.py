"""Thin profiling surface.

The profile computation lives in :mod:`analysis.duckdb_engine` (it shares the
DuckDB connection logic with schema extraction). This module re-exports it so
callers can import ``profile_dataset`` from a dedicated ``analysis.profile``
namespace if they prefer, without duplicating logic.
"""
from analysis.duckdb_engine import extract_schema, profile_dataset

__all__ = ["profile_dataset", "extract_schema"]
