"""Unit tests for session store (replacing old SQL-safety tests)."""
import pandas as pd


def test_store_put_and_get():
    from sessions import store
    store._SESSION_STORE.clear()
    df = pd.DataFrame({"col": [1, 2, 3]})
    store.put("t1", df)
    assert store.get("t1") is not None


def test_store_delete():
    from sessions import store
    store._SESSION_STORE.clear()
    df = pd.DataFrame({"col": [1]})
    store.put("t2", df)
    store.delete("t2")
    assert store.get("t2") is None


def test_store_get_missing():
    from sessions import store
    store._SESSION_STORE.clear()
    assert store.get("missing-key") is None
