import pytest

from data.sql_guard import SqlNotAllowed, assert_read_only


def test_plain_select_passes():
    assert assert_read_only("SELECT * FROM ds_x") == "SELECT * FROM ds_x"


def test_with_cte_select_passes():
    sql = "WITH x AS (SELECT region FROM ds_x) SELECT * FROM x"
    assert assert_read_only(sql).startswith("WITH")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM ds_x",
        "DROP TABLE ds_x",
        "UPDATE ds_x SET a = 1",
        "INSERT INTO ds_x VALUES (1)",
        "ALTER TABLE ds_x ADD COLUMN b TEXT",
        "ATTACH DATABASE 'x.db' AS y",
        "PRAGMA table_info(ds_x)",
        "CREATE TABLE evil (a TEXT)",
    ],
)
def test_dml_and_ddl_rejected(sql):
    with pytest.raises(SqlNotAllowed):
        assert_read_only(sql)


def test_stacked_statement_rejected():
    with pytest.raises(SqlNotAllowed):
        assert_read_only("SELECT 1; DROP TABLE t")


def test_comment_hidden_statement_rejected():
    with pytest.raises(SqlNotAllowed):
        assert_read_only("SELECT 1 -- ok\n; DROP TABLE t")


def test_case_insensitive_rejection():
    with pytest.raises(SqlNotAllowed):
        assert_read_only("dElEtE FROM ds_x")


def test_empty_rejected():
    with pytest.raises(SqlNotAllowed):
        assert_read_only("   ")
