"""Tests for the rules engine."""

from safequery.config import SafeQueryConfig
from safequery.parser import parse_sql
from safequery.rules import RulesEngine


def _check(sql: str, config=None) -> list:
    config = config or SafeQueryConfig.default()
    parsed = parse_sql(sql, dialect=config.dialect)
    engine = RulesEngine()
    return engine.evaluate(parsed, config)


class TestBlockRules:
    def test_delete_without_where(self):
        violations = _check("DELETE FROM users")
        rules = [v.rule for v in violations]
        assert "delete_without_where" in rules
        block_v = next(v for v in violations if v.rule == "delete_without_where")
        assert block_v.action == "BLOCK"
        assert block_v.severity == "critical"

    def test_update_without_where(self):
        violations = _check("UPDATE users SET active = false")
        rules = [v.rule for v in violations]
        assert "update_without_where" in rules

    def test_drop_table(self):
        violations = _check("DROP TABLE users")
        rules = [v.rule for v in violations]
        assert "drop_table" in rules

    def test_truncate(self):
        violations = _check("TRUNCATE TABLE users")
        rules = [v.rule for v in violations]
        assert "truncate" in rules

    def test_update_where_1_eq_1(self):
        violations = _check("UPDATE users SET active = false WHERE 1=1")
        rules = [v.rule for v in violations]
        assert "update_without_where" in rules

    def test_alter_table_drop_column(self):
        violations = _check("ALTER TABLE users DROP COLUMN email")
        rules = [v.rule for v in violations]
        assert "alter_table_drop_column" in rules
        v = next(v for v in violations if v.rule == "alter_table_drop_column")
        assert v.action == "BLOCK"
        assert v.severity == "critical"

    def test_alter_table_drop_column_not_triggered_by_add(self):
        violations = _check("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
        rules = [v.rule for v in violations]
        assert "alter_table_drop_column" not in rules

    def test_delete_all_rows_where_1_eq_1(self):
        violations = _check("DELETE FROM users WHERE 1=1")
        rules = [v.rule for v in violations]
        assert "delete_all_rows" in rules
        v = next(v for v in violations if v.rule == "delete_all_rows")
        assert v.action == "BLOCK"

    def test_delete_all_rows_where_true(self):
        violations = _check("DELETE FROM users WHERE true")
        rules = [v.rule for v in violations]
        assert "delete_all_rows" in rules


class TestWarnRules:
    def test_delete_without_limit(self):
        violations = _check("DELETE FROM users WHERE id > 100")
        rules = [v.rule for v in violations]
        assert "delete_without_limit" in rules

    def test_update_without_limit(self):
        violations = _check("UPDATE users SET active = false WHERE id > 100")
        rules = [v.rule for v in violations]
        assert "update_without_limit" in rules

    def test_protected_table_modification(self):
        violations = _check("DELETE FROM users WHERE id = 1")
        rules = [v.rule for v in violations]
        assert "protected_table_modification" in rules

    def test_update_all_rows_where_1_eq_1(self):
        violations = _check("UPDATE orders SET status = 'cancelled' WHERE 1=1")
        rules = [v.rule for v in violations]
        assert "update_all_rows" in rules
        v = next(v for v in violations if v.rule == "update_all_rows")
        assert v.action == "WARN"
        assert v.severity == "high"

    def test_update_all_rows_where_true(self):
        violations = _check("UPDATE orders SET status = 'cancelled' WHERE true")
        rules = [v.rule for v in violations]
        assert "update_all_rows" in rules

    def test_large_in_clause(self):
        values = ", ".join(str(i) for i in range(101))
        sql = f"SELECT * FROM users WHERE id IN ({values})"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "large_in_clause" in rules
        v = next(v for v in violations if v.rule == "large_in_clause")
        assert v.action == "WARN"

    def test_small_in_clause_no_violation(self):
        values = ", ".join(str(i) for i in range(10))
        sql = f"SELECT id FROM orders WHERE id IN ({values})"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "large_in_clause" not in rules

    def test_cross_join_explicit(self):
        violations = _check("SELECT * FROM users CROSS JOIN orders")
        rules = [v.rule for v in violations]
        assert "cross_join" in rules
        v = next(v for v in violations if v.rule == "cross_join")
        assert v.action == "WARN"

    def test_cross_join_implicit(self):
        violations = _check("SELECT * FROM users, orders")
        rules = [v.rule for v in violations]
        assert "cross_join" in rules

    def test_grant_all(self):
        violations = _check("GRANT ALL PRIVILEGES ON users TO admin")
        rules = [v.rule for v in violations]
        assert "grant_all" in rules
        v = next(v for v in violations if v.rule == "grant_all")
        assert v.action == "WARN"


class TestLogRules:
    def test_select_star(self):
        violations = _check("SELECT * FROM users")
        rules = [v.rule for v in violations]
        assert "select_star" in rules

    def test_multiple_table_join(self):
        sql = """
        SELECT u.id, o.id, p.id, l.id
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        JOIN logs l ON u.id = l.user_id
        """
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "multiple_table_join" in rules
        v = next(v for v in violations if v.rule == "multiple_table_join")
        assert v.action == "LOG"

    def test_two_table_join_no_violation(self):
        sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "multiple_table_join" not in rules

    def test_union_without_limit(self):
        sql = "SELECT id FROM users UNION SELECT id FROM orders"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "union_without_limit" in rules
        v = next(v for v in violations if v.rule == "union_without_limit")
        assert v.action == "LOG"

    def test_union_with_limit_no_violation(self):
        sql = "SELECT id FROM users UNION SELECT id FROM orders LIMIT 10"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "union_without_limit" not in rules

    def test_deep_subquery(self):
        sql = "SELECT id FROM (SELECT id FROM (SELECT id FROM (SELECT id FROM users)))"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "deep_subquery" in rules
        v = next(v for v in violations if v.rule == "deep_subquery")
        assert v.action == "LOG"

    def test_shallow_subquery_no_violation(self):
        sql = "SELECT id FROM (SELECT id FROM users)"
        violations = _check(sql)
        rules = [v.rule for v in violations]
        assert "deep_subquery" not in rules


class TestSafeQueries:
    def test_select_with_columns(self):
        violations = _check("SELECT id, name FROM users WHERE id = 1")
        assert len(violations) == 0

    def test_insert(self):
        violations = _check("INSERT INTO logs (msg) VALUES ('hello')")
        assert len(violations) == 0
