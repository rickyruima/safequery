"""Tests for the SQL parser module."""

from safequery.parser import parse_sql


class TestParseStatementType:
    def test_select(self):
        result = parse_sql("SELECT id FROM users WHERE id = 1")
        assert result.statement_type == "SELECT"

    def test_delete(self):
        result = parse_sql("DELETE FROM users WHERE id = 1")
        assert result.statement_type == "DELETE"

    def test_update(self):
        result = parse_sql("UPDATE users SET name = 'x' WHERE id = 1")
        assert result.statement_type == "UPDATE"

    def test_insert(self):
        result = parse_sql("INSERT INTO users (name) VALUES ('x')")
        assert result.statement_type == "INSERT"

    def test_drop(self):
        result = parse_sql("DROP TABLE users")
        assert result.statement_type == "DROP"

    def test_truncate(self):
        result = parse_sql("TRUNCATE TABLE users")
        assert result.statement_type == "TRUNCATE"


class TestParseWhereClause:
    def test_has_where(self):
        result = parse_sql("DELETE FROM users WHERE id = 1")
        assert result.has_where is True

    def test_no_where(self):
        result = parse_sql("DELETE FROM users")
        assert result.has_where is False

    def test_where_1_eq_1(self):
        result = parse_sql("UPDATE users SET active = false WHERE 1=1")
        assert result.has_where is False  # tautology


class TestParseTables:
    def test_single_table(self):
        result = parse_sql("SELECT * FROM users")
        assert "users" in result.tables

    def test_multiple_tables(self):
        result = parse_sql("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        assert "users" in result.tables
        assert "orders" in result.tables


class TestParseLimit:
    def test_has_limit(self):
        result = parse_sql("DELETE FROM users WHERE id > 100 LIMIT 10")
        assert result.has_limit is True

    def test_no_limit(self):
        result = parse_sql("DELETE FROM users WHERE id > 100")
        assert result.has_limit is False


class TestSelectStar:
    def test_select_star(self):
        result = parse_sql("SELECT * FROM users")
        assert result.is_select_star is True

    def test_select_columns(self):
        result = parse_sql("SELECT id, name FROM users")
        assert result.is_select_star is False


class TestSubqueryDepth:
    def test_no_subquery(self):
        result = parse_sql("SELECT id FROM users")
        assert result.subquery_depth == 0

    def test_one_level(self):
        result = parse_sql("SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)")
        assert result.subquery_depth >= 1


class TestParseError:
    def test_invalid_sql(self):
        result = parse_sql("NOT VALID SQL AT ALL !!!")
        # sqlglot is lenient, may not error. Just verify it doesn't crash.
        assert result.raw_sql == "NOT VALID SQL AT ALL !!!"
