"""Unit tests for the in-memory session store — no DB or LLM calls."""
import pandas as pd
import pytest


def test_put_and_get():
    from sessions import store
    store._SESSION_STORE.clear()
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    store.put("sess-1", df)
    result = store.get("sess-1")
    assert result is not None
    assert list(result.columns) == ["a", "b"]
    assert len(result) == 2


def test_get_missing_returns_none():
    from sessions import store
    store._SESSION_STORE.clear()
    assert store.get("nonexistent") is None


def test_delete_removes_entry():
    from sessions import store
    store._SESSION_STORE.clear()
    df = pd.DataFrame({"x": [10]})
    store.put("sess-del", df)
    assert store.get("sess-del") is not None
    store.delete("sess-del")
    assert store.get("sess-del") is None


def test_delete_nonexistent_is_noop():
    from sessions import store
    store._SESSION_STORE.clear()
    # Should not raise
    store.delete("not-there")


def test_put_overwrites_existing():
    from sessions import store
    store._SESSION_STORE.clear()
    df1 = pd.DataFrame({"col": [1]})
    df2 = pd.DataFrame({"col": [2, 3]})
    store.put("same-id", df1)
    store.put("same-id", df2)
    result = store.get("same-id")
    assert len(result) == 2
    assert result["col"].iloc[0] == 2


def test_multiple_sessions_isolated():
    from sessions import store
    store._SESSION_STORE.clear()
    df_a = pd.DataFrame({"a": [1]})
    df_b = pd.DataFrame({"b": [2]})
    store.put("session-a", df_a)
    store.put("session-b", df_b)
    assert "a" in store.get("session-a").columns
    assert "b" in store.get("session-b").columns


def test_dataframe_stored_by_reference():
    """DataFrame should be the same object (no copy overhead)."""
    from sessions import store
    store._SESSION_STORE.clear()
    df = pd.DataFrame({"z": [99]})
    store.put("ref-test", df)
    assert store.get("ref-test") is df
