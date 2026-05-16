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


class TestLogRules:
    def test_select_star(self):
        violations = _check("SELECT * FROM users")
        rules = [v.rule for v in violations]
        assert "select_star" in rules


class TestSafeQueries:
    def test_select_with_columns(self):
        violations = _check("SELECT id, name FROM users WHERE id = 1")
        assert len(violations) == 0

    def test_insert(self):
        violations = _check("INSERT INTO logs (msg) VALUES ('hello')")
        assert len(violations) == 0
